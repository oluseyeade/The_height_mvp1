from pkg.extensions import db
from pkg.models.apartment import Category, Facility, Apartment, ApartmentImage


def seed_default_apartments():
    db.create_all()

    categories_data = [
        {'name': 'Penthouse', 'description': 'Premium penthouse suite with bespoke luxury finishes.', 'icon': 'fa-crown', 'order': 1},
        {'name': 'Executive Suite', 'description': 'Executive shortlet for business stays and premium comfort.', 'icon': 'fa-briefcase', 'order': 2},
        {'name': 'Deluxe Apartment', 'description': 'Deluxe apartment with refined lifestyle features.', 'icon': 'fa-couch', 'order': 3},
        {'name': 'Studio Apartment', 'description': 'Compact modern studio for city convenience.', 'icon': 'fa-bed', 'order': 4},
    ]

    created_categories = {}
    for cdata in categories_data:
        cat = Category.query.filter_by(name=cdata['name']).first()
        if not cat:
            cat = Category(
                name=cdata['name'],
                description=cdata['description'],
                icon=cdata['icon'],
                sort_order=cdata['order']
            )
            db.session.add(cat)
        created_categories[cdata['name']] = cat

    db.session.commit()

    facilities = [
        'Starlink High-Speed',
        'CCTV',
        'Secure Parking',
        '24/7 Power Supply',
        'Secure Underground Parking',
        'Concierge Service',
    ]
    for fac_name in facilities:
        if not Facility.query.filter_by(name=fac_name).first():
            db.session.add(Facility(name=fac_name, icon='fa-circle-check'))

    db.session.commit()

    samples = [
        {
            'title': 'The Penthouse Royal Suite',
            'category_name': 'Penthouse',
            'price': 150000,
            'bedrooms': 3,
            'bathrooms': 3,
            'capacity': 6,
            'desc': 'Experience panoramic skyline views, private plunge pool, and bespoke luxury furnishing in our flagship Penthouse Suite.',
            'image': 'https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=1200&q=80',
            'is_featured': True,
        },
        {
            'title': 'Executive Oceanfront Loft',
            'category_name': 'Executive Suite',
            'price': 110000,
            'bedrooms': 2,
            'bathrooms': 2,
            'capacity': 4,
            'desc': 'Premium finished executive suite with smart TVs, modern kitchen, and high-speed connectivity.',
            'image': 'https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80',
            'is_featured': True,
        },
        {
            'title': 'Deluxe Ambassador Suite',
            'category_name': 'Deluxe Apartment',
            'price': 95000,
            'bedrooms': 2,
            'bathrooms': 2,
            'capacity': 4,
            'desc': 'Elegant deluxe apartment with full kitchen amenities, marble bath finishes, and premium comfort.',
            'image': 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80',
            'is_featured': False,
        },
        {
            'title': 'Urban Chic Studio',
            'category_name': 'Studio Apartment',
            'price': 55000,
            'bedrooms': 1,
            'bathrooms': 1,
            'capacity': 2,
            'desc': 'Minimalist luxury studio optimized for shortlet travelers seeking privacy and central city accessibility.',
            'image': 'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=80',
            'is_featured': False,
        },
    ]

    for sample in samples:
        existing_apt = Apartment.query.filter_by(title=sample['title']).first()
        if not existing_apt:
            category = created_categories.get(sample['category_name'])
            apt = Apartment(
                title=sample['title'],
                category_id=category.category_id,
                price_per_night=sample['price'],
                bedrooms=sample['bedrooms'],
                bathrooms=sample['bathrooms'],
                capacity=sample['capacity'],
                description=sample['desc'],
                is_featured=sample['is_featured'],
                status='available'
            )
            db.session.add(apt)
            db.session.commit()

            img = ApartmentImage(
                apartment_id=apt.apartment_id,
                image_url=sample['image'],
                is_cover=True,
                caption='Living Room View'
            )
            db.session.add(img)
            db.session.commit()

    print('Sample apartments seeded.')
