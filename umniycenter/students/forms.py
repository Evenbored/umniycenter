from django import forms
from groups.models import SchoolGroups


class CustomUserSearchForm(forms.Form):
    USERSTATUS = (
        (True, "Активный"),
        (False, "Неактивный"),
    )
    course = forms.ModelChoiceField(
        queryset=SchoolGroups.objects.none(),
        widget=forms.Select(attrs={'class': 'student-list-select', 
                                               'placeholder': 'Курс', 'id': 'class',})
    )
    status = forms.ChoiceField(choices=USERSTATUS,initial=0,
                               widget=forms.Select(attrs={'class': 'student-list-select', 
                                               'placeholder': 'Курс', 'id': 'status',}))

    
    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('queryset', None)
        super().__init__(*args, **kwargs)

        if queryset:
            self.fields['course'].queryset = queryset
