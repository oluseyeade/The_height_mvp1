from pkg.repositories.apartment_repository import ApartmentRepository, CategoryRepository, FacilityRepository
from pkg.models.apartment import Apartment, Category, Amenity, Facility, ApartmentImage, ApartmentAmenity, ApartmentFacility
from pkg.services.audit_service import AuditService
from pkg.utils.file_upload import save_uploaded_image
from pkg.extensions import db

class ApartmentService:
    def __init__(self):
        self.apt_repo = ApartmentRepository()
        self.cat_repo = CategoryRepository()
        self.fac_repo = FacilityRepository()

    def get_all_apartments(self):
        return self.apt_repo.get_all()

    def get_available_apartments(self):
        return self.apt_repo.get_available_apartments()

    def get_apartment_by_id(self, apartment_id, increment_views=False):
        if increment_views:
            return self.apt_repo.increment_view_count(apartment_id)
        return self.apt_repo.get_by_id(apartment_id)

    def create_apartment(self, title, description, price_per_night, category_id, bedrooms=1, bathrooms=1, capacity=2, square_feet=None, admin_user_id=None):
        apartment = Apartment(
            title=title.strip(),
            description=description.strip(),
            price_per_night=float(price_per_night),
            category_id=int(category_id),
            bedrooms=int(bedrooms),
            bathrooms=int(bathrooms),
            capacity=int(capacity),
            square_feet=int(square_feet) if square_feet else None,
            created_by=admin_user_id,
            updated_by=admin_user_id
        )
        self.apt_repo.add(apartment)
        self.apt_repo.commit()

        if admin_user_id:
            AuditService.log_activity(
                user_id=admin_user_id,
                activity_type='APARTMENT_CREATE',
                description=f"Apartment '{apartment.title}' created.",
                module='Apartment',
                action='create'
            )
        return True, "Apartment created successfully.", apartment

    def update_apartment(self, apartment_id, title, description, price_per_night, category_id, status, bedrooms, bathrooms, capacity, admin_user_id=None):
        apt = self.apt_repo.get_by_id(apartment_id)
        if not apt:
            return False, "Apartment not found.", None

        apt.title = title.strip()
        apt.description = description.strip()
        apt.price_per_night = float(price_per_night)
        apt.category_id = int(category_id)
        apt.status = status
        apt.bedrooms = int(bedrooms)
        apt.bathrooms = int(bathrooms)
        apt.capacity = int(capacity)
        apt.updated_by = admin_user_id

        self.apt_repo.commit()

        if admin_user_id:
            AuditService.log_activity(
                user_id=admin_user_id,
                activity_type='APARTMENT_UPDATE',
                description=f"Apartment '{apt.title}' updated.",
                module='Apartment',
                action='update'
            )
        return True, "Apartment updated successfully.", apt

    def upload_apartment_images(self, apartment_id, image_files, caption=None, is_cover=False, admin_user_id=None):
        apt = self.apt_repo.get_by_id(apartment_id)
        if not apt:
            return False, "Apartment not found."

        uploaded_count = 0
        for file in image_files:
            rel_path = save_uploaded_image(file, folder_name='apartment_images')
            if rel_path:
                img = ApartmentImage(
                    apartment_id=apartment_id,
                    image_url=rel_path,
                    caption=caption or 'Room Image',
                    is_cover=is_cover and (uploaded_count == 0),
                    uploaded_by=admin_user_id
                )
                db.session.add(img)
                uploaded_count += 1

        db.session.commit()
        return True, f"Successfully uploaded {uploaded_count} images for '{apt.title}'."

    def get_categories(self):
        return self.cat_repo.get_active_categories()

    def get_facilities(self):
        return self.fac_repo.get_active_facilities()
