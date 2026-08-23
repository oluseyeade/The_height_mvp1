from pkg.extensions import db

class BaseRepository:
    def __init__(self, model):
        self.model = model

    def get_by_id(self, entity_id):
        return self.model.query.get(entity_id)

    def get_all(self):
        return self.model.query.all()

    def filter_by(self, **kwargs):
        return self.model.query.filter_by(**kwargs).all()

    def find_one(self, **kwargs):
        return self.model.query.filter_by(**kwargs).first()

    def add(self, entity):
        db.session.add(entity)
        return entity

    def update(self, entity):
        db.session.add(entity)
        return entity

    def delete(self, entity):
        db.session.delete(entity)

    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()
