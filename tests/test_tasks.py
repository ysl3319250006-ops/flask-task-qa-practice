"""Flask integration checks using a separate in-memory SQLite database."""
import pytest
from app import app, db
from models import Task
from sqlalchemy import create_engine


@pytest.fixture()
def client():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        original_engine = db.engines[None]
        test_engine = create_engine("sqlite:///:memory:")
        db.engines[None] = test_engine
        try:
            db.create_all()
            yield app.test_client()
        finally:
            db.session.remove()
            db.drop_all()
            test_engine.dispose()
            db.engines[None] = original_engine


def test_add_task_and_list(client):
    response = client.post('/add', data={'title': 'Review', 'desc': 'Check booking'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'Review' in response.data
    with app.app_context():
        assert Task.query.count() == 1


def test_empty_title_is_rejected(client):
    response = client.post('/add', data={'title': '', 'desc': 'Description'})
    assert response.status_code == 200
    with app.app_context():
        assert Task.query.count() == 0


def test_empty_description_is_rejected(client):
    response = client.post('/add', data={'title': 'Review', 'desc': ''})
    assert response.status_code == 200
    with app.app_context():
        assert Task.query.count() == 0


def test_edit_persists_new_fields(client):
    client.post('/add', data={'title': 'Before', 'desc': 'Old'})
    with app.app_context():
        task_id = Task.query.first().id
    response = client.post(f'/edit/{task_id}', data={'title': 'After', 'desc': 'New'}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        task = db.session.get(Task, task_id)
        assert (task.title, task.desc) == ('After', 'New')


def test_delete_requires_post(client):
    client.post('/add', data={'title': 'Temporary', 'desc': 'Delete me'})
    with app.app_context():
        task_id = Task.query.first().id
    assert client.get(f'/delete=/{task_id}').status_code == 200
    with app.app_context():
        assert db.session.get(Task, task_id) is not None
    assert client.post(f'/delete=/{task_id}', follow_redirects=True).status_code == 200
    with app.app_context():
        assert db.session.get(Task, task_id) is None


def test_missing_task_redirects_without_changing_data(client):
    response = client.get('/edit/999', follow_redirects=True)
    assert response.status_code == 200
    assert b'Task not found' in response.data
    with app.app_context():
        assert Task.query.count() == 0
