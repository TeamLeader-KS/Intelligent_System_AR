import pytest

from app.manage import LOCAL_KEYS, prepare_local_files


def test_local_files_keep_passwords_on_restart(tmp_path):
    directory = tmp_path / "secrets"
    prepare_local_files(directory)
    before = {key: (directory / key).read_bytes() for key in LOCAL_KEYS}
    assert all(len(value) == 48 for value in before.values())
    assert len(set(before.values())) == len(LOCAL_KEYS)
    prepare_local_files(directory)
    assert {key: (directory / key).read_bytes() for key in LOCAL_KEYS} == before


def test_invalid_existing_password_is_not_replaced(tmp_path):
    path = tmp_path / LOCAL_KEYS[0]
    path.write_text("broken")
    with pytest.raises(ValueError, match=LOCAL_KEYS[0]):
        prepare_local_files(tmp_path)
    assert path.read_text() == "broken"
