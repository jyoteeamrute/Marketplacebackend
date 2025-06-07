from django import forms
from django.contrib.auth.hashers import make_password

from .models import ProfessionalUser


class ProfessionalUserAdminForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False,
        label="New Password",
        widget=forms.PasswordInput,
        help_text="Leave blank if you don't want to change the password."
    )

    class Meta:
        model = ProfessionalUser
        fields = '__all__'

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = self.cleaned_data.get('new_password')
        if new_password:
            user.password = make_password(new_password)
        if commit:
            user.save()
        return user
