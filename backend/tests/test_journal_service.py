"""Unit tests for JournalService (trade journal notes and tags)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.journal_service import JournalService, PREDEFINED_TAGS


class FakeTag:
    """Fake Tag ORM object for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.user_id = kwargs.get("user_id", uuid.uuid4())
        self.name = kwargs.get("name", "test-tag")
        self.created_at = kwargs.get("created_at", datetime.utcnow())


class FakeTransactionNote:
    """Fake TransactionNote ORM object for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.transaction_id = kwargs.get("transaction_id", uuid.uuid4())
        self.note = kwargs.get("note", "")
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())


class FakeTransaction:
    """Fake Transaction ORM object for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.user_id = kwargs.get("user_id", uuid.uuid4())


class FakeResult:
    """Fake SQLAlchemy result wrapper."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._value, list):
            return self._value
        return [self._value] if self._value else []


class TestAttachNote:
    """Tests for JournalService.attach_note."""

    @pytest.mark.asyncio
    async def test_attach_new_note(self):
        """Attaching a note to a transaction without one creates a new note."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()
        tx = FakeTransaction(id=tx_id, user_id=user_id)

        # First execute: _get_user_transaction
        # Second execute: check for existing note (none)
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(tx),
                FakeResult(None),
            ]
        )

        service = JournalService(db)
        result = await service.attach_note(user_id, tx_id, "My trade reasoning")

        db.add.assert_called_once()
        added_note = db.add.call_args[0][0]
        assert added_note.note == "My trade reasoning"
        assert added_note.transaction_id == tx_id

    @pytest.mark.asyncio
    async def test_update_existing_note(self):
        """Updating an existing note modifies it in place."""
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()
        tx = FakeTransaction(id=tx_id, user_id=user_id)
        existing_note = FakeTransactionNote(
            transaction_id=tx_id, note="Old note"
        )

        db.execute = AsyncMock(
            side_effect=[
                FakeResult(tx),
                FakeResult(existing_note),
            ]
        )

        service = JournalService(db)
        result = await service.attach_note(user_id, tx_id, "Updated reasoning")

        assert existing_note.note == "Updated reasoning"

    @pytest.mark.asyncio
    async def test_note_exceeds_1000_chars_rejected(self):
        """A note longer than 1000 chars is rejected."""
        db = AsyncMock()

        service = JournalService(db)
        long_note = "x" * 1001

        with pytest.raises(HTTPException) as exc_info:
            await service.attach_note(uuid.uuid4(), uuid.uuid4(), long_note)

        assert exc_info.value.status_code == 400
        assert "1000" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_empty_note_rejected(self):
        """An empty note is rejected."""
        db = AsyncMock()

        service = JournalService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.attach_note(uuid.uuid4(), uuid.uuid4(), "   ")

        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_note_exactly_1000_chars_accepted(self):
        """A note with exactly 1000 chars is accepted."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()
        tx = FakeTransaction(id=tx_id, user_id=user_id)

        db.execute = AsyncMock(
            side_effect=[
                FakeResult(tx),
                FakeResult(None),
            ]
        )

        service = JournalService(db)
        note_text = "x" * 1000
        result = await service.attach_note(user_id, tx_id, note_text)

        db.add.assert_called_once()
        added_note = db.add.call_args[0][0]
        assert len(added_note.note) == 1000

    @pytest.mark.asyncio
    async def test_note_on_nonexistent_transaction_rejected(self):
        """Attaching a note to a non-existent transaction raises 404."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(None))

        service = JournalService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.attach_note(uuid.uuid4(), uuid.uuid4(), "A note")

        assert exc_info.value.status_code == 404


class TestSetTags:
    """Tests for JournalService.set_tags."""

    @pytest.mark.asyncio
    async def test_set_tags_on_transaction(self):
        """Setting tags replaces existing ones."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.delete = AsyncMock()

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()
        tx = FakeTransaction(id=tx_id, user_id=user_id)

        tag1 = FakeTag(id=uuid.uuid4(), user_id=user_id, name="Momentum")
        tag2 = FakeTag(id=uuid.uuid4(), user_id=user_id, name="Value")

        # Calls:
        # 1. _get_user_transaction
        # 2. get existing transaction tags (empty)
        # 3. verify tag_ids belong to user
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(tx),
                FakeResult([]),
                FakeResult([tag1, tag2]),
            ]
        )

        service = JournalService(db)
        result = await service.set_tags(
            user_id, tx_id, [str(tag1.id), str(tag2.id)]
        )

        assert len(result) == 2
        assert tag1 in result
        assert tag2 in result

    @pytest.mark.asyncio
    async def test_set_empty_tags_clears_existing(self):
        """Setting empty tag list removes all existing tags."""
        db = AsyncMock()
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()
        tx = FakeTransaction(id=tx_id, user_id=user_id)

        db.execute = AsyncMock(
            side_effect=[
                FakeResult(tx),
                FakeResult([]),
            ]
        )

        service = JournalService(db)
        result = await service.set_tags(user_id, tx_id, [])

        assert result == []

    @pytest.mark.asyncio
    async def test_set_tags_invalid_id_rejected(self):
        """Setting tags with an invalid UUID raises 400."""
        db = AsyncMock()

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()
        tx = FakeTransaction(id=tx_id, user_id=user_id)

        db.execute = AsyncMock(
            side_effect=[
                FakeResult(tx),
                FakeResult([]),
            ]
        )

        service = JournalService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.set_tags(user_id, tx_id, ["not-a-uuid"])

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_set_tags_other_users_tag_rejected(self):
        """Setting a tag that doesn't belong to the user raises 400."""
        db = AsyncMock()
        db.delete = AsyncMock()

        user_id = uuid.uuid4()
        tx_id = uuid.uuid4()
        tx = FakeTransaction(id=tx_id, user_id=user_id)
        other_tag_id = uuid.uuid4()

        # _get_user_transaction, existing tags (empty), verify tags (returns empty - not found)
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(tx),
                FakeResult([]),
                FakeResult([]),  # No valid tags found for user
            ]
        )

        service = JournalService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.set_tags(user_id, tx_id, [str(other_tag_id)])

        assert exc_info.value.status_code == 400
        assert "do not belong to user" in exc_info.value.detail


class TestCreateTag:
    """Tests for JournalService.create_tag."""

    @pytest.mark.asyncio
    async def test_create_tag_success(self):
        """Creating a valid tag succeeds."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        # Check uniqueness returns no existing tag
        db.execute = AsyncMock(return_value=FakeResult(None))

        service = JournalService(db)
        user_id = uuid.uuid4()
        result = await service.create_tag(user_id, "My Custom Tag")

        db.add.assert_called_once()
        added_tag = db.add.call_args[0][0]
        assert added_tag.name == "My Custom Tag"
        assert added_tag.user_id == user_id

    @pytest.mark.asyncio
    async def test_create_tag_duplicate_rejected(self):
        """Creating a duplicate tag (case-insensitive) raises 409."""
        db = AsyncMock()
        existing_tag = FakeTag(name="momentum")
        db.execute = AsyncMock(return_value=FakeResult(existing_tag))

        service = JournalService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_tag(uuid.uuid4(), "Momentum")

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_create_tag_too_long_rejected(self):
        """A tag name > 50 chars is rejected."""
        db = AsyncMock()

        service = JournalService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_tag(uuid.uuid4(), "x" * 51)

        assert exc_info.value.status_code == 400
        assert "50" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_tag_empty_name_rejected(self):
        """A blank tag name is rejected."""
        db = AsyncMock()

        service = JournalService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_tag(uuid.uuid4(), "   ")

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_tag_exactly_50_chars_accepted(self):
        """A tag name with exactly 50 chars is accepted."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(None))

        service = JournalService(db)
        tag_name = "x" * 50
        result = await service.create_tag(uuid.uuid4(), tag_name)

        db.add.assert_called_once()
        added_tag = db.add.call_args[0][0]
        assert len(added_tag.name) == 50

    @pytest.mark.asyncio
    async def test_create_tag_single_char_accepted(self):
        """A tag name with 1 char is accepted."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(None))

        service = JournalService(db)
        result = await service.create_tag(uuid.uuid4(), "A")

        db.add.assert_called_once()
        added_tag = db.add.call_args[0][0]
        assert added_tag.name == "A"


class TestDeleteTag:
    """Tests for JournalService.delete_tag."""

    @pytest.mark.asyncio
    async def test_delete_existing_tag(self):
        """Deleting a tag owned by user succeeds."""
        db = AsyncMock()
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        user_id = uuid.uuid4()
        tag = FakeTag(user_id=user_id)
        db.execute = AsyncMock(return_value=FakeResult(tag))

        service = JournalService(db)
        await service.delete_tag(user_id, tag.id)

        db.delete.assert_called_once_with(tag)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_tag_raises_404(self):
        """Deleting a non-existent tag raises 404."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult(None))

        service = JournalService(db)

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_tag(uuid.uuid4(), uuid.uuid4())

        assert exc_info.value.status_code == 404


class TestListTags:
    """Tests for JournalService.list_tags."""

    @pytest.mark.asyncio
    async def test_list_tags_includes_predefined(self):
        """Listing tags with include_predefined=True includes predefined tags."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = JournalService(db)
        result = await service.list_tags(uuid.uuid4(), include_predefined=True)

        # Should have all predefined tags
        predefined_names = [t["name"] for t in result if t["is_predefined"]]
        assert set(predefined_names) == set(PREDEFINED_TAGS)

    @pytest.mark.asyncio
    async def test_list_tags_excludes_predefined(self):
        """Listing tags with include_predefined=False excludes predefined tags."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=FakeResult([]))

        service = JournalService(db)
        result = await service.list_tags(uuid.uuid4(), include_predefined=False)

        predefined = [t for t in result if t.get("is_predefined")]
        assert predefined == []

    @pytest.mark.asyncio
    async def test_list_tags_includes_custom_tags(self):
        """Listing tags includes user's custom tags."""
        db = AsyncMock()
        user_id = uuid.uuid4()
        custom_tag = FakeTag(user_id=user_id, name="My Custom")
        db.execute = AsyncMock(return_value=FakeResult([custom_tag]))

        service = JournalService(db)
        result = await service.list_tags(user_id, include_predefined=False)

        assert len(result) == 1
        assert result[0]["name"] == "My Custom"
        assert result[0]["is_predefined"] is False


class TestPredefinedTags:
    """Tests for predefined tag constants."""

    def test_predefined_tags_exist(self):
        """PREDEFINED_TAGS has expected values."""
        assert len(PREDEFINED_TAGS) > 0
        assert "Earnings Play" in PREDEFINED_TAGS
        assert "Momentum" in PREDEFINED_TAGS
        assert "Value" in PREDEFINED_TAGS
        assert "Dividend" in PREDEFINED_TAGS
        assert "Speculative" in PREDEFINED_TAGS
        assert "Technical" in PREDEFINED_TAGS

    def test_predefined_tags_are_within_length_limits(self):
        """All predefined tags are 1-50 characters."""
        for tag in PREDEFINED_TAGS:
            assert 1 <= len(tag) <= 50, f"Predefined tag '{tag}' outside 1-50 chars"
