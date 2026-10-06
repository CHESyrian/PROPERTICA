from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Account, AccountType


class RegisterForm(UserCreationForm):
    account_type = forms.ChoiceField(
        choices=AccountType.choices,
        widget=forms.RadioSelect,
        initial=AccountType.PERSONAL,
        label="Account type",
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "name@example.com", "autocomplete": "email"}),
    )

    class Meta:
        model = Account
        fields = ("email", "account_type", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update(
            {"placeholder": "••••••••", "autocomplete": "new-password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"placeholder": "••••••••", "autocomplete": "new-password"}
        )

    def save(self, commit=True):
        user = Account.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            account_type=self.cleaned_data["account_type"],
        )
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={"placeholder": "name@example.com", "autocomplete": "email"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].widget.attrs.update(
            {"placeholder": "••••••••", "autocomplete": "current-password"}
        )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ("display_name", "phone")
        widgets = {
            "display_name": forms.TextInput(attrs={"placeholder": "Public name (Agency / Agent)"}),
            "phone": forms.TextInput(attrs={"placeholder": "+963 …"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = kwargs.get("instance")
        if user and user.account_type == AccountType.PERSONAL:
            self.fields["display_name"].help_text = (
                "Personal accounts show their USR username publicly. "
                "This field is optional and not used on listings."
            )
        if user and user.account_type == AccountType.AGENT and user.agency_id:
            self.fields["display_name"].help_text = (
                "Your public name is managed by your agency while linked."
            )
            self.fields["display_name"].disabled = True
