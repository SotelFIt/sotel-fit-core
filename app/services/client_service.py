from sqlalchemy.orm import Session
from models.client import Client

def get_all_clients(db: Session):
    return db.query(Client).all()

def get_client_by_id(db: Session, client_id: int):
    return db.query(Client).filter(Client.id == client_id).first()

def create_new_client(db: Session, client_data):
    new_client = Client(
        name=client_data.name,
        status=client_data.status,
        age=client_data.age,
        weight=client_data.weight,
        height=client_data.height,
        goal=client_data.goal
    )
    db.add(new_client)
    db.commit()
    db.refresh(new_client)
    return new_client

def update_existing_client(db: Session, client_id: int, client_data):
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        client.name = client_data.name
        client.status = client_data.status
        client.age = client_data.age
        client.weight = client_data.weight
        client.height = client_data.height
        client.goal = client_data.goal
        db.commit()
        db.refresh(client)
    return client

def delete_existing_client(db: Session, client_id: int):
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        db.delete(client)
        db.commit()
    return client