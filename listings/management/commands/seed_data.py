"""
Seed property categories, attribute definitions, free plan entitlements,
and a few sample listings for development.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Account, AccountType, Plan, PlanEntitlement
from listings.models import (
    AttributeDefinition,
    Listing,
    ListingStatus,
    PropertyCategory,
    PropertyParentGroup,
)


CATEGORIES = [
    ("house", "House", PropertyParentGroup.RESIDENTIAL),
    ("apartment", "Apartment", PropertyParentGroup.RESIDENTIAL),
    ("land_residential", "Residential Land", PropertyParentGroup.LAND),
    ("commercial_office", "Office", PropertyParentGroup.COMMERCIAL),
    ("commercial_retail", "Retail / Storefront", PropertyParentGroup.COMMERCIAL),
]

HOUSE_ATTRS = [
    ("bedrooms", "number", True, 1, "Bedrooms"),
    ("bathrooms", "number", True, 2, "Bathrooms"),
    ("living_area_m2", "number", True, 3, "Living area (m²)"),
    ("year_built", "number", False, 4, "Year built"),
    ("parking_spaces", "number", False, 5, "Parking spaces"),
    ("furnished", "boolean", False, 6, "Furnished"),
]

APARTMENT_ATTRS = HOUSE_ATTRS  # same for MVP

LAND_ATTRS = [
    ("lot_size_m2", "number", True, 1, "Lot size (m²)"),
    ("zoning_type", "enum", True, 2, "Zoning"),
    ("road_access", "boolean", False, 3, "Road access"),
]

OFFICE_ATTRS = [
    ("floor_area_m2", "number", True, 1, "Floor area (m²)"),
    ("ceiling_height_m", "number", False, 2, "Ceiling height (m)"),
    ("parking_spaces", "number", False, 3, "Parking spaces"),
]


class Command(BaseCommand):
    help = "Seed categories, attributes, free plan, and sample data"

    def handle(self, *args, **options):
        self.stdout.write("Seeding plans…")
        plan, created = Plan.objects.get_or_create(
            code="free",
            defaults={"label": "Free", "applies_to": "all", "is_active": True},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("  Created free plan"))
        PlanEntitlement.objects.get_or_create(
            plan=plan,
            entitlement_key="max_active_listings",
            defaults={"entitlement_value": "10"},
        )
        PlanEntitlement.objects.get_or_create(
            plan=plan,
            entitlement_key="can_feature_listing",
            defaults={"entitlement_value": "false"},
        )

        starter, created = Plan.objects.get_or_create(
            code="starter",
            defaults={"label": "Starter", "applies_to": "all", "is_active": True},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("  Created starter plan"))
        PlanEntitlement.objects.get_or_create(
            plan=starter,
            entitlement_key="max_active_listings",
            defaults={"entitlement_value": "50"},
        )
        PlanEntitlement.objects.get_or_create(
            plan=starter,
            entitlement_key="can_feature_listing",
            defaults={"entitlement_value": "true"},
        )

        self.stdout.write("Seeding categories & attributes…")
        cat_map = {}
        for code, label, group in CATEGORIES:
            cat, _ = PropertyCategory.objects.get_or_create(
                code=code,
                defaults={"label": label, "parent_group": group},
            )
            cat_map[code] = cat

        def seed_attrs(cat, attrs, enum_opts=None):
            for key, dtype, required, order, label in attrs:
                opts = None
                if dtype == "enum" and key == "zoning_type":
                    opts = ["residential", "agricultural", "industrial"]
                AttributeDefinition.objects.get_or_create(
                    category=cat,
                    attribute_key=key,
                    defaults={
                        "data_type": dtype,
                        "is_required": required,
                        "display_order": order,
                        "label": label,
                        "enum_options": opts,
                    },
                )

        seed_attrs(cat_map["house"], HOUSE_ATTRS)
        seed_attrs(cat_map["apartment"], APARTMENT_ATTRS)
        seed_attrs(cat_map["land_residential"], LAND_ATTRS)
        seed_attrs(cat_map["commercial_office"], OFFICE_ATTRS)
        seed_attrs(cat_map["commercial_retail"], OFFICE_ATTRS)

        self.stdout.write("Seeding demo users & listings…")
        if not Account.objects.filter(email="demo@example.com").exists():
            seller = Account.objects.create_user(
                email="demo@example.com",
                password="demo1234",
                account_type=AccountType.PERSONAL,
            )
            self.stdout.write(f"  Demo seller: {seller.username} / demo@example.com / demo1234")
        else:
            seller = Account.objects.get(email="demo@example.com")

        samples = [
            {
                "title": "Sunny 3-bedroom family house with garden",
                "category": "house",
                "price": Decimal("425000"),
                "city": "Rotterdam",
                "region": "South Holland",
                "country": "Netherlands",
                "area_value": Decimal("145"),
                "type_attributes": {
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "living_area_m2": 145,
                    "year_built": 2008,
                    "parking_spaces": 1,
                    "furnished": False,
                },
            },
            {
                "title": "Modern city-centre apartment",
                "category": "apartment",
                "price": Decimal("289000"),
                "city": "Amsterdam",
                "region": "North Holland",
                "country": "Netherlands",
                "area_value": Decimal("78"),
                "type_attributes": {
                    "bedrooms": 2,
                    "bathrooms": 1,
                    "living_area_m2": 78,
                    "year_built": 2019,
                    "furnished": True,
                },
            },
            {
                "title": "Residential building plot near park",
                "category": "land_residential",
                "price": Decimal("175000"),
                "city": "Utrecht",
                "region": "Utrecht",
                "country": "Netherlands",
                "area_value": Decimal("450"),
                "type_attributes": {
                    "lot_size_m2": 450,
                    "zoning_type": "residential",
                    "road_access": True,
                },
            },
        ]

        for data in samples:
            cat = cat_map[data["category"]]
            if not Listing.objects.filter(title=data["title"]).exists():
                Listing.objects.create(
                    owner=seller,
                    category=cat,
                    title=data["title"],
                    description=f"Beautiful {data['title'].lower()}. Contact for viewing.",
                    price=data["price"],
                    currency="EUR",
                    negotiable=True,
                    city=data["city"],
                    region=data["region"],
                    country=data["country"],
                    area_value=data["area_value"],
                    type_attributes=data["type_attributes"],
                    status=ListingStatus.ACTIVE,
                    published_at=timezone.now(),
                )
                self.stdout.write(f"  Created listing: {data['title']}")

        self.stdout.write(self.style.SUCCESS("Seed complete."))
