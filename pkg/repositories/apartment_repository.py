from pkg.repositories.base_repository import BaseRepository
from pkg.models.apartment import Apartment, Category, Amenity, Facility, ApartmentImage, ApartmentAmenity, ApartmentFacility

class ApartmentRepository(BaseRepository):
    def __init__(self):
        super().__init__(Apartment)

    def get_available_apartments(self):
        return Apartment.query.filter_by(status='available').all()

    def get_featured_apartments(self):
        return Apartment.query.filter_by(is_featured=True, status='available').all()

    def find_by_category(self, category_id):
        return Apartment.query.filter_by(category_id=category_id, status='available').all()

    def increment_view_count(self, apartment_id):
        apt = self.get_by_id(apartment_id)
        if apt:
            apt.view_count = (apt.view_count or 0) + 1
            self.commit()
        return apt

class CategoryRepository(BaseRepository):
    def __init__(self):
        super().__init__(Category)

    def get_active_categories(self):
        return Category.query.filter_by(is_active=True).order_by(Category.sort_order.asc()).all()

class FacilityRepository(BaseRepository):
    def __init__(self):
        super().__init__(Facility)

    def get_active_facilities(self):
        return Facility.query.filter_by(is_active=True).all()
