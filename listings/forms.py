"""Forms for the multi-step listing creation wizard."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError

from .models import AttributeDefinition, Listing, PropertyCategory


class ListingWizardForm(forms.Form):
    """
    Single form covering all wizard steps.
    Step visibility is handled in the template (Alpine.js).
    """

    # Step 1 — Category
    category = forms.ModelChoiceField(
        queryset=PropertyCategory.objects.all(),
        empty_label=None,
        widget=forms.RadioSelect,
        label="Property type",
    )

    # Step 2 — Basic details
    title = forms.CharField(max_length=200, label="Title")
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        required=False,
        label="Description",
    )
    price = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Price",
    )
    currency = forms.ChoiceField(
        choices=[
            ("EUR", "EUR"),
            ("USD", "USD"),
            ("GBP", "GBP"),
            ("CHF", "CHF"),
        ],
        initial="EUR",
        label="Currency",
    )
    negotiable = forms.BooleanField(required=False, initial=False, label="Price is negotiable")

    # Step 3 — Location
    address_line = forms.CharField(max_length=255, required=False, label="Street address")
    city = forms.CharField(max_length=100, label="City")
    region = forms.CharField(max_length=100, required=False, label="Region / State")
    country = forms.CharField(max_length=100, initial="Syria", label="Country")
    latitude = forms.DecimalField(
        max_digits=9, decimal_places=6, required=False, label="Latitude"
    )
    longitude = forms.DecimalField(
        max_digits=9, decimal_places=6, required=False, label="Longitude"
    )

    # Step 4 — Type attributes are dynamic; collected as type_attributes_* fields
    # and assembled in clean(). area_value is common/searchable.
    area_value = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        label="Area (m²)",
        help_text="Overall area used for search filters",
    )

    # Step 5 — Photos (handled separately via files in the view)
    # cover_index indicates which uploaded file is the cover (0-based)
    cover_index = forms.IntegerField(required=False, initial=0, widget=forms.HiddenInput)

    # Step 6 — action
    action = forms.ChoiceField(
        choices=[("draft", "Save as draft"), ("publish", "Publish")],
        initial="draft",
        widget=forms.HiddenInput,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.attribute_defs: list[AttributeDefinition] = kwargs.pop("attribute_defs", [])
        super().__init__(*args, **kwargs)

        # Dynamically add fields for each attribute definition
        for defn in self.attribute_defs:
            field_name = f"attr_{defn.attribute_key}"
            label = defn.label or defn.attribute_key.replace("_", " ").title()
            required = defn.is_required

            if defn.data_type == AttributeDefinition.DataType.NUMBER:
                self.fields[field_name] = forms.DecimalField(
                    required=required,
                    label=label,
                    max_digits=12,
                    decimal_places=2,
                )
            elif defn.data_type == AttributeDefinition.DataType.BOOLEAN:
                self.fields[field_name] = forms.BooleanField(
                    required=False,
                    label=label,
                )
            elif defn.data_type == AttributeDefinition.DataType.ENUM:
                choices = [(o, o.replace("_", " ").title()) for o in (defn.enum_options or [])]
                self.fields[field_name] = forms.ChoiceField(
                    choices=[("", "—")] + choices,
                    required=required,
                    label=label,
                )
            else:  # string
                self.fields[field_name] = forms.CharField(
                    required=required,
                    label=label,
                    max_length=255,
                )

    def clean(self):
        cleaned = super().clean()
        # Assemble type_attributes from dynamic fields
        type_attributes = {}
        for defn in self.attribute_defs:
            field_name = f"attr_{defn.attribute_key}"
            value = cleaned.get(field_name)
            if value is None or value == "":
                if defn.is_required:
                    self.add_error(field_name, "This field is required.")
                continue
            if defn.data_type == AttributeDefinition.DataType.NUMBER:
                try:
                    # Store as int when whole number, else float
                    d = Decimal(str(value))
                    type_attributes[defn.attribute_key] = int(d) if d == d.to_integral_value() else float(d)
                except (InvalidOperation, TypeError):
                    self.add_error(field_name, "Enter a valid number.")
            elif defn.data_type == AttributeDefinition.DataType.BOOLEAN:
                type_attributes[defn.attribute_key] = bool(value)
            else:
                type_attributes[defn.attribute_key] = value

        cleaned["type_attributes"] = type_attributes
        return cleaned


class ListingEditForm(forms.ModelForm):
    """Edit an existing listing (dashboard)."""

    class Meta:
        model = Listing
        fields = [
            "title",
            "description",
            "price",
            "currency",
            "negotiable",
            "address_line",
            "city",
            "region",
            "country",
            "latitude",
            "longitude",
            "area_value",
        ]
