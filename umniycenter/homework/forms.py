
from django import forms

from accounts.models import CustomUser
from groups.models import SchoolGroups


class HomeWorkAddForm(forms.Form):
    course = forms.ModelChoiceField(
        required=True,
        queryset=SchoolGroups.objects.none(),
        widget=forms.Select()
    )
    student = forms.ModelChoiceField(
        required=True,
        queryset=CustomUser.objects.none(),
        widget=forms.SelectMultiple()
    )
    dateend = forms.DateTimeField(
        widget=forms.DateInput()
    )