from django import forms


class ContactSellerForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Hi, is this property still available? I would like to schedule a viewing…",
                "class": "contact-textarea",
            }
        ),
        min_length=10,
        max_length=2000,
        label="Your message",
    )


class ReplyForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Write a reply…",
                "class": "contact-textarea",
            }
        ),
        min_length=1,
        max_length=2000,
        label="",
    )
