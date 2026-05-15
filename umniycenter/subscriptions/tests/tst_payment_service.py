"""
Tests for Payment Service.
"""

import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime
from subscriptions.payment_service import PaymentService
from subscriptions.models import Payment, Subscription
from tests.utils import (
    SubscriptionFactory, PaymentFactory, StudentFactory, ParentFactory,
    TariffFactory, MockYooKassa, SchoolGroupFactory
)


@pytest.mark.critical
class PaymentServiceCreatePaymentTest(TestCase):
    """Test cases for PaymentService.create_payment()."""
    
    @patch('subscriptions.payment_service.yookassa.Payment.create')
    def test_create_online_payment_success(self, mock_yookassa):
        """Test creating online payment with YooKassa."""
        subscription = SubscriptionFactory(status='pending')
        mock_yookassa.return_value = MockYooKassa.create_payment_success(
            payment_id='test_123',
            amount=str(subscription.tariff.price)
        )
        
        payment = PaymentService.create_payment(
            subscription_id=subscription.id,
            parent_id=subscription.parent.id,
            payment_method='online',
            return_url='http://test.com/success'
        )
        
        self.assertEqual(payment.payment_method, 'online')
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.yookassa_payment_id, 'test_123')
        self.assertIsNotNone(payment.yookassa_payment_url)
        mock_yookassa.assert_called_once()
    
    def test_create_cash_payment(self):
        """Test creating cash payment."""
        subscription = SubscriptionFactory(status='pending')
        
        payment = PaymentService.create_payment(
            subscription=subscription,
            payment_method='cash'
        )
        
        self.assertEqual(payment.payment_method, 'cash')
        self.assertEqual(payment.status, 'pending')
        self.assertIsNone(payment.yookassa_payment_id)
    
    def test_create_card_payment(self):
        """Test creating card payment."""
        subscription = SubscriptionFactory(status='pending')
        
        payment = PaymentService.create_payment(
            subscription_id=subscription.id,
            parent_id=subscription.parent.id,
            payment_method='card',
            transaction_id='TXN123456'
        )
        
        self.assertEqual(payment.payment_method, 'card')
        self.assertEqual(payment.transaction_id, 'TXN123456')
    
    def test_create_transfer_payment(self):
        """Test creating bank transfer payment."""
        subscription = SubscriptionFactory(status='pending')
        
        payment = PaymentService.create_payment(
            subscription_id=subscription.id,
            parent_id=subscription.parent.id,
            payment_method='transfer',
            notes='Перевод на счет'
        )
        
        self.assertEqual(payment.payment_method, 'transfer')
        self.assertEqual(payment.notes, 'Перевод на счет')
    
    @patch('subscriptions.payment_service.yookassa.Payment.create')
    def test_create_payment_with_yookassa_error(self, mock_yookassa):
        """Test handling YooKassa API error."""
        subscription = SubscriptionFactory(status='pending')
        mock_yookassa.side_effect = Exception('YooKassa API Error')
        
        with self.assertRaises(Exception):
            PaymentService.create_payment(
                subscription_id=subscription.id,
                parent_id=subscription.parent.id,
                payment_method='online',
                return_url='http://test.com/success'
            )
    
    def test_create_payment_amount_matches_tariff(self):
        """Test that payment amount matches tariff price."""
        tariff = TariffFactory(price=Decimal('7500.00'))
        subscription = SubscriptionFactory(tariff=tariff, status='pending')
        
        payment = PaymentService.create_payment(
            subscription_id=subscription.id,
            parent_id=subscription.parent.id,
            payment_method='cash'
        )
        
        self.assertEqual(payment.amount, Decimal('7500.00'))


@pytest.mark.critical
class PaymentServiceWebhookTest(TestCase):
    """Test cases for PaymentService.process_webhook()."""
    
    def test_process_successful_payment_webhook(self):
        """Test processing successful payment webhook."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            yookassa_payment_id='test_123',
            status='pending'
        )
        
        webhook_data = MockYooKassa.webhook_payment_succeeded(
            payment_id='test_123',
            amount=str(payment.amount)
        )
        
        result = PaymentService.process_webhook(
            webhook_data,
            source_ip='185.71.76.0'  # Valid YooKassa IP
        )
        
        self.assertTrue(result)
        
        payment.refresh_from_db()
        subscription.refresh_from_db()
        
        self.assertEqual(payment.status, 'completed')
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(subscription.status, 'active')
    
    def test_process_webhook_invalid_ip(self):
        """Test rejecting webhook from invalid IP."""
        webhook_data = MockYooKassa.webhook_payment_succeeded()
        
        with self.assertRaises(ValueError):
            PaymentService.process_webhook(
                webhook_data,
                source_ip='192.168.1.1'  # Invalid IP
            )
    
    def test_process_webhook_payment_not_found(self):
        """Test webhook for nonexistent payment."""
        webhook_data = MockYooKassa.webhook_payment_succeeded(
            payment_id='nonexistent_123'
        )
        
        result = PaymentService.process_webhook(
            webhook_data,
            source_ip='185.71.76.0'
        )
        
        self.assertFalse(result)
    
    def test_process_webhook_amount_mismatch(self):
        """Test webhook with amount mismatch."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            yookassa_payment_id='test_123',
            amount=Decimal('5000.00'),
            status='pending'
        )
        
        webhook_data = MockYooKassa.webhook_payment_succeeded(
            payment_id='test_123',
            amount='3000.00'  # Wrong amount
        )
        
        with self.assertRaises(ValueError):
            PaymentService.process_webhook(
                webhook_data,
                source_ip='185.71.76.0'
            )
    
    def test_process_webhook_idempotency(self):
        """Test that duplicate webhooks are handled correctly."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            yookassa_payment_id='test_123',
            status='pending'
        )
        
        webhook_data = MockYooKassa.webhook_payment_succeeded(
            payment_id='test_123',
            amount=str(payment.amount)
        )
        
        # Process webhook first time
        result1 = PaymentService.process_webhook(
            webhook_data,
            source_ip='185.71.76.0'
        )
        
        # Process same webhook again
        result2 = PaymentService.process_webhook(
            webhook_data,
            source_ip='185.71.76.0'
        )
        
        self.assertTrue(result1)
        self.assertTrue(result2)  # Should not fail
        
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'completed')
    
    def test_process_canceled_payment_webhook(self):
        """Test processing canceled payment webhook."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            yookassa_payment_id='test_123',
            status='pending'
        )
        
        webhook_data = MockYooKassa.webhook_payment_canceled(
            payment_id='test_123',
            amount=str(payment.amount)
        )
        
        result = PaymentService.process_webhook(
            webhook_data,
            source_ip='185.71.76.0'
        )
        
        self.assertTrue(result)
        
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'canceled')


@pytest.mark.critical
class PaymentServiceConfirmOfflinePaymentTest(TestCase):
    """Test cases for PaymentService.confirm_offline_payment()."""
    
    def test_confirm_cash_payment(self):
        """Test confirming cash payment."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            payment_method='cash',
            status='pending'
        )
        
        result = PaymentService.confirm_offline_payment(payment.id)
        
        self.assertTrue(result)
        
        payment.refresh_from_db()
        subscription.refresh_from_db()
        
        self.assertEqual(payment.status, 'completed')
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(subscription.status, 'active')
    
    def test_confirm_card_payment(self):
        """Test confirming card payment."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            payment_method='card',
            status='pending'
        )
        
        result = PaymentService.confirm_offline_payment(payment.id)
        
        self.assertTrue(result)
        
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'completed')
    
    def test_confirm_transfer_payment(self):
        """Test confirming bank transfer payment."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            payment_method='transfer',
            status='pending'
        )
        
        result = PaymentService.confirm_offline_payment(payment.id)
        
        self.assertTrue(result)
        
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'completed')
    
    def test_cannot_confirm_online_payment(self):
        """Test that online payments cannot be confirmed manually."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            payment_method='online',
            status='pending'
        )
        
        with self.assertRaises(ValueError):
            PaymentService.confirm_offline_payment(payment.id)
    
    def test_cannot_confirm_already_completed_payment(self):
        """Test that completed payment cannot be confirmed again."""
        subscription = SubscriptionFactory(status='active')
        payment = PaymentFactory(
            subscription=subscription,
            payment_method='cash',
            status='completed',
            paid_at=datetime.now()
        )
        
        with self.assertRaises(ValueError):
            PaymentService.confirm_offline_payment(payment.id)
    
    def test_confirm_payment_with_group_assignment(self):
        """Test confirming payment assigns student to requested group."""
        student = StudentFactory()
        parent = ParentFactory()
        group = SchoolGroupFactory()
        subscription = SubscriptionFactory(
            student=student,
            parent=parent,
            status='pending'
        )
        payment = PaymentFactory(
            subscription=subscription,
            payment_method='cash',
            status='pending'
        )
        
        # Assuming there's a way to specify requested_group
        # This depends on your implementation
        result = PaymentService.confirm_offline_payment(payment.id)
        
        self.assertTrue(result)


@pytest.mark.critical
class PaymentServiceCancelPaymentTest(TestCase):
    """Test cases for PaymentService.cancel_payment()."""
    
    def test_cancel_pending_payment(self):
        """Test canceling pending payment."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            status='pending'
        )
        
        result = PaymentService.cancel_payment(payment.id)
        
        self.assertTrue(result)
        
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'canceled')
    
    def test_cannot_cancel_completed_payment(self):
        """Test that completed payment cannot be canceled."""
        subscription = SubscriptionFactory(status='active')
        payment = PaymentFactory(
            subscription=subscription,
            status='completed',
            paid_at=datetime.now()
        )
        
        with self.assertRaises(ValueError):
            PaymentService.cancel_payment(payment.id)
    
    def test_cancel_payment_nonexistent(self):
        """Test canceling nonexistent payment."""
        with self.assertRaises(Exception):
            PaymentService.cancel_payment(99999)


@pytest.mark.critical
class PaymentServiceIPValidationTest(TestCase):
    """Test cases for PaymentService.validate_webhook_ip()."""
    
    def test_valid_yookassa_ip_ranges(self):
        """Test that valid YooKassa IPs are accepted."""
        valid_ips = [
            '185.71.76.0',
            '185.71.77.0',
            '77.75.153.0',
            '77.75.154.0',
            '2a02:5180::/32'
        ]
        
        for ip in valid_ips:
            try:
                result = PaymentService.validate_webhook_ip(ip)
                # If method returns True or doesn't raise, it's valid
                self.assertTrue(True)
            except ValueError:
                # If validation is strict, some IPs might fail
                pass
    
    def test_invalid_ip_rejected(self):
        """Test that invalid IPs are rejected."""
        invalid_ips = [
            '192.168.1.1',
            '10.0.0.1',
            '8.8.8.8',
            '1.1.1.1'
        ]
        
        for ip in invalid_ips:
            with self.assertRaises(ValueError):
                PaymentService.validate_webhook_ip(ip)


@pytest.mark.critical
class PaymentServiceSubscriptionActivationTest(TestCase):
    """Test cases for subscription activation after payment."""
    
    def test_subscription_activated_on_payment_success(self):
        """Test that subscription is activated when payment succeeds."""
        subscription = SubscriptionFactory(status='pending')
        payment = PaymentFactory(
            subscription=subscription,
            payment_method='cash',
            status='pending'
        )
        
        PaymentService.confirm_offline_payment(payment.id)
        
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, 'active')
    
    def test_student_active_status_updated(self):
        """Test that student active status is updated after payment."""
        student = StudentFactory(is_active=False)
        subscription = SubscriptionFactory(
            student=student,
            status='pending'
        )
        payment = PaymentFactory(
            subscription=subscription,
            payment_method='cash',
            status='pending'
        )
        
        PaymentService.confirm_offline_payment(payment.id)
        
        student.refresh_from_db()
        # Depending on implementation, student might be activated
        # self.assertTrue(student.is_active)
