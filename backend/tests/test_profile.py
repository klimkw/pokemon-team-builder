import asyncio
import pytest
from app.api import profile


def test_profile_password_work_runs_outside_event_loop(signed_in, monkeypatch):
    original = profile.PasswordHelper
    calls = []

    class CheckedHelper:
        def verify_and_update(self, *args):
            with pytest.raises(RuntimeError, match='no running event loop'):
                asyncio.get_running_loop()
            calls.append('verify')
            return original().verify_and_update(*args)

        def hash(self, password):
            with pytest.raises(RuntimeError, match='no running event loop'):
                asyncio.get_running_loop()
            calls.append('hash')
            return original().hash(password)

    monkeypatch.setattr(profile, 'PasswordHelper', CheckedHelper)
    response = signed_in.patch('/api/profile', json={
        'current_password': 'long-test-password', 'new_password': 'changed-test-password'})
    assert response.status_code == 200
    assert calls == ['verify', 'hash']
    assert signed_in.get('/api/auth/me').status_code == 401



@pytest.mark.parametrize('username', ['ab', 'a' * 33, 'space name', 'éclair', 'ash\n'])
def test_registration_and_profile_share_username_rules(signed_in, username):
    assert signed_in.post('/api/auth/register', json={
        'username': username, 'password': 'long-test-password'}).status_code == 422
    assert signed_in.patch('/api/profile', json={
        'username': username, 'current_password': 'long-test-password'}).status_code == 422



@pytest.mark.parametrize('password', ['a' * 7, 'a' * 129])
def test_registration_and_profile_share_password_length_rules(signed_in, password):
    assert signed_in.post('/api/auth/register', json={
        'username': 'brock', 'password': password}).status_code == 422
    assert signed_in.patch('/api/profile', json={
        'current_password': 'long-test-password', 'new_password': password}).status_code == 422
