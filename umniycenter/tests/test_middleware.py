"""
Tests for middleware.
"""

import pytest
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from umniycenter.middleware import ApiAjaxOnlyMiddleware


@pytest.mark.security
class ApiAjaxOnlyMiddlewareTest(TestCase):
    """Test cases for ApiAjaxOnlyMiddleware."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ApiAjaxOnlyMiddleware(get_response=lambda r: HttpResponse())
    
    def test_allows_xmlhttprequest(self):
        """Test that XMLHttpRequest is allowed."""
        request = self.factory.get('/api/v1/test/')
        request.META['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_allows_json_content_type(self):
        """Test that requests with application/json content-type are allowed."""
        request = self.factory.post('/api/v1/test/', content_type='application/json')
        
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_allows_json_accept_header(self):
        """Test that requests with application/json accept header are allowed."""
        request = self.factory.get('/api/v1/test/')
        request.META['HTTP_ACCEPT'] = 'application/json'
        
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_blocks_direct_browser_access(self):
        """Test that direct browser access is blocked."""
        request = self.factory.get('/api/v1/test/')
        # No special headers
        
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 400)
    
    def test_allows_non_api_urls(self):
        """Test that non-API URLs are allowed."""
        request = self.factory.get('/accounts/login/')
        
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_allows_admin_urls(self):
        """Test that admin URLs are allowed."""
        request = self.factory.get('/admin/')
        
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_blocks_api_without_proper_headers(self):
        """Test that API requests without proper headers are blocked."""
        request = self.factory.get('/api/v1/students/')
        request.META['HTTP_ACCEPT'] = 'text/html'
        
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 400)
    
    def test_allows_api_post_with_json(self):
        """Test that API POST with JSON is allowed."""
        request = self.factory.post(
            '/api/v1/students/',
            data='{"name": "test"}',
            content_type='application/json'
        )
        
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
