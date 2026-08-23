from datetime import datetime, timezone
from pkg.extensions import db

class Category(db.Model):
    __tablename__ = 'categories'

    category_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(50), nullable=True, default='fa-building')
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    apartments = db.relationship('Apartment', backref='category', lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"


class Apartment(db.Model):
    __tablename__ = 'apartments'

    apartment_id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price_per_night = db.Column(db.Float, nullable=False)
    bedrooms = db.Column(db.Integer, default=1, nullable=False)
    bathrooms = db.Column(db.Integer, default=1, nullable=False)
    capacity = db.Column(db.Integer, default=2, nullable=False)
    square_feet = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(30), default='available', nullable=False)  # available, booked, maintenance, renovation
    view_count = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    featured_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    images = db.relationship('ApartmentImage', backref='apartment', lazy=True, cascade='all, delete-orphan')
    amenities = db.relationship('ApartmentAmenity', backref='apartment', lazy=True, cascade='all, delete-orphan')
    facilities = db.relationship('ApartmentFacility', backref='apartment', lazy=True, cascade='all, delete-orphan')

    @property
    def cover_image(self):
        cover = next((img for img in self.images if img.is_cover), None)
        if cover:
            return cover.image_url
        if self.images:
            return self.images[0].image_url
        return 'https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80'

    def __repr__(self):
        return f"<Apartment {self.title} (₦{self.price_per_night})>"


class ApartmentImage(db.Model):
    __tablename__ = 'apartment_images'

    image_id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    image_url = db.Column(db.String(255), nullable=False)
    is_cover = db.Column(db.Boolean, default=False)
    caption = db.Column(db.String(150), nullable=True)  # e.g., Master Bedroom, Living Room, Kitchen
    sort_order = db.Column(db.Integer, default=0)
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<ApartmentImage apt_id={self.apartment_id} url={self.image_url}>"


class Amenity(db.Model):
    __tablename__ = 'amenities'

    amenity_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    icon = db.Column(db.String(50), nullable=True, default='fa-check')
    category = db.Column(db.String(50), default='General')  # Entertainment, Connectivity, Safety, Comfort
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Amenity {self.name}>"


class Facility(db.Model):
    __tablename__ = 'facilities'

    facility_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    icon = db.Column(db.String(50), nullable=True, default='fa-concierge-bell')
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Facility {self.name}>"


class ApartmentAmenity(db.Model):
    __tablename__ = 'apartment_amenities'

    id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    amenity_id = db.Column(db.Integer, db.ForeignKey('amenities.amenity_id'), nullable=False)

    amenity_info = db.relationship('Amenity', backref='apartment_associations')


class ApartmentFacility(db.Model):
    __tablename__ = 'apartment_facilities'

    id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey('facilities.facility_id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    facility_info = db.relationship('Facility', backref='apartment_associations')
