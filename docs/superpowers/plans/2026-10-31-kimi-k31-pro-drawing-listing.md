# Kimi K3.1 Pro Drawing and Listing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fixed-deadline drawing sessions, validated PNG/layer saving, private draft access, IndexedDB-backed Canvas editing, and transactional artwork listing to the independent Kimi project.

**Architecture:** Flask routes authenticate requests and delegate state transitions to artwork services. PNG/ZIP validation and filesystem writes live behind one `save_artwork` transaction; browser code owns drawing and temporary recovery but never controls the deadline. Listing creates the artwork/auction state change and first-listing bonus atomically.

**Tech Stack:** Phase 1 Flask application, SQLAlchemy, Flask-Login, Flask-WTF, Jinja2, Canvas, IndexedDB, native JavaScript, Pytest.

## Global Constraints

- Work only in `HEW2026_v1.0_Chatbox_KimiK3.1Pro/`; do not modify MiniMax or restore historical Kimi files.
- Canvas is 1024×1024; durations are 10, 30, 60, and 300 seconds.
- Maximum 10 layers; composite PNG and each layer PNG are at most 5 MiB; uncompressed layer total is at most 50 MiB.
- The server deadline never extends during recovery; final-save retry grace is 60 seconds.
- Saved artwork cannot be edited again in Ver0.5.
- Draft images and layer ZIP files are outside `static/` and require owner authorization.
- Drawing bonus is 100 pt once per Asia/Tokyo calendar day; first-listing bonus is 300 pt once per user.
- Listing creates one active auction per artwork; title, description, existing tags, start price, and duration are validated server-side.
- All POST requests require CSRF outside tests; tests use isolated temporary databases and upload directories.
- No Git commits or pushes unless explicitly requested.
- Execute inline in the current session, using the already selected execution preference.

---

### Task 1: Drawing Session Model and Fixed Deadline

**Files:**
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/models/artwork.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/models/__init__.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/artwork_service.py`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_drawing_sessions.py`

**Interfaces:**
- Produces: `Artwork`, `DrawingSession`, `create_drawing_session(user, duration_seconds, now=None) -> DrawingSession`, `session_is_saveable(session, now=None) -> bool`.

- [ ] Write tests proving 10/30/60/300 seconds are accepted, other durations raise `BusinessError`, `deadline_at == created_at + duration`, and expiration uses the 60-second grace only for saving.

```python
def test_session_has_fixed_deadline(app):
    with app.app_context():
        user, _ = register_user("drawer", "password123")
        session = create_drawing_session(user, 30)
        assert session.duration_seconds == 30
        assert session.deadline_at == session.created_at + timedelta(seconds=30)
        assert session_is_saveable(session, now=session.deadline_at + timedelta(seconds=59))
        assert not session_is_saveable(session, now=session.deadline_at + timedelta(seconds=61))
```

- [ ] Run `.venv/Scripts/python -m pytest tests/test_drawing_sessions.py -q`; expected failure is missing `app.models.artwork`.
- [ ] Implement `Artwork(id, user_id, title, description, status, image_path, layers_path, created_at)` and `DrawingSession(id, user_id, artwork_id, duration_seconds, created_at, deadline_at)` with `artwork.status == "drawing"`.
- [ ] Implement session creation with `deadline_at = created_at + timedelta(seconds=duration)` and saveability with `now <= deadline_at + timedelta(seconds=60)`.
- [ ] Run the new tests and all Phase 1 tests; expected all pass.

### Task 2: PNG, Layer ZIP, and Bonus Transaction

**Files:**
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/image_service.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/layer_service.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/artwork_service.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/config.py`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_artwork_save.py`

**Interfaces:**
- Produces: `validate_png(data: bytes) -> None`, `build_layers_zip(layers: list[dict]) -> bytes`, `save_artwork(session, composite: bytes, layers: list[dict], now=None) -> Artwork`.

- [ ] Write tests with generated PNG bytes for valid save, invalid signature, non-1024 dimensions, empty layers, more than 10 layers, repeated save rejection, and one drawing bonus per JST day.

```python
def test_valid_save_creates_private_files_and_bonus(app):
    with app.app_context():
        user, _ = register_user("drawer", "password123")
        session = create_drawing_session(user, 30)
        artwork = save_artwork(session, png_1024(), [{"name": "Layer 1", "png": png_1024(), "opacity": 100, "visible": True}])
        assert artwork.status == "draft"
        assert Path(artwork.image_path).exists()
        assert Path(artwork.layers_path).exists()
        assert user.points == 1100


def test_second_save_is_rejected(app):
    with app.app_context():
        user, _ = register_user("drawer", "password123")
        session = create_drawing_session(user, 30)
        save_artwork(session, png_1024(), [{"name": "Layer 1", "png": png_1024()}])
        with pytest.raises(BusinessError, match="保存"):
            save_artwork(session, png_1024(), [{"name": "Layer 1", "png": png_1024()}])
```

- [ ] Run `.venv/Scripts/python -m pytest tests/test_artwork_save.py -q`; expected failure is missing image/layer services.
- [ ] Implement PNG signature and IHDR width/height validation without decoding untrusted data through Pillow.
- [ ] Implement deterministic `layers/001.png` naming and `manifest.json` containing name/order/visibility/opacity; reject oversized and malformed layers.
- [ ] Save under the configured per-test `UPLOAD_DIR`, grant `drawing:{user.id}:{YYYY-MM-DD}` at 100 pt, and mark the artwork `draft` in the same database transaction.
- [ ] Run all tests; expected all pass.

### Task 3: Authenticated Drawing and Private File Routes

**Files:**
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/artworks/__init__.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/artworks/forms.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/artworks/routes.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/__init__.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/artworks/setup.html`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/artworks/canvas.html`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_artwork_routes.py`

**Interfaces:**
- Produces: `GET/POST /artworks/draw`, `GET /artworks/session/<id>`, `POST /artworks/session/<id>/save`, `GET /artworks/<id>/image`, `GET /artworks/<id>/layers`.

- [ ] Write route tests for login redirects, owner-only canvas access, valid save, non-owner 403 image/ZIP responses, and missing artwork 404.
- [ ] Run the route tests and verify failure from absent Blueprint routes.
- [ ] Implement routes using the Task 1–2 interfaces; accept multipart `composite` and `layers_json`, return JSON `{artwork_id, redirect_url}` on successful save, and never expose raw filesystem paths.
- [ ] Render the duration form and Canvas bootstrap with `data-session-id`, `data-deadline`, `data-save-url`, and CSRF header value.
- [ ] Run all tests; expected all pass.

### Task 4: Canvas Tools, Layers, Undo/Redo, and IndexedDB

**Files:**
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/static/js/canvas.js`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/artworks/canvas.html`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/static/css/app.css`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_canvas_contract.py`

**Interfaces:**
- Produces: browser `window.HEWCanvas` with `addLayer()`, `removeLayer()`, `undo()`, `redo()`, `save()`, and `destroy()`.

- [ ] Write static contract tests verifying four tools, layer controls, pointer events, 50-state history cap, IndexedDB database name, server-deadline countdown, and multipart save field names.

```python
def test_canvas_uses_server_deadline_and_indexeddb():
    source = (ROOT / "app/static/js/canvas.js").read_text(encoding="utf-8")
    assert 'indexedDB.open("hew-kimi-canvas", 1)' in source
    assert "new Date(root.dataset.deadline)" in source
    assert 'history.splice(0, history.length - 50)' in source
    assert 'formData.append("composite"' in source
    assert 'formData.append("layers_json"' in source
```

- [ ] Run the contract test and verify it fails because `canvas.js` is absent.
- [ ] Implement pointer drawing, G-pen, round-pen, blur, eraser, layer visibility/order/opacity, 50-operation history, IndexedDB recovery keyed by session ID, and deadline-aware save without extending the server deadline.
- [ ] Build responsive Japanese tool controls and accessible layer buttons in the Canvas template.
- [ ] Run all tests and the preview smoke gate; expected all pass.

### Task 5: Tags, Listing Validation, and Auction Creation

**Files:**
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/models/tag.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/models/auction.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/models/__init__.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/services/artwork_service.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/artworks/forms.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/artworks/routes.py`
- Create: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/artworks/listing.html`
- Test: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tests/test_listing.py`

**Interfaces:**
- Produces: `Tag`, `ArtworkTag`, `Auction`, `list_artwork(user, artwork, title, description, tag_ids, start_price, duration_minutes, now=None) -> Auction`; `GET/POST /artworks/<id>/listing`.

- [ ] Write tests proving only the draft owner can list, title/price/duration/tags are validated, listing changes `draft -> listed` and creates one active auction, and the first-listing bonus is exactly 300 pt once.
- [ ] Run listing tests and verify failure from missing tag/auction models.
- [ ] Implement models and `list_artwork`; allow 5/10/15/20 minutes, positive integer start price, and only existing tag IDs. Use unique `artwork_id` on `auctions` and `first_listing:{user.id}` wallet reference.
- [ ] Implement Japanese listing form and redirect to the auction detail endpoint `/auctions/<id>`; Phase 3 owns the full detail page.
- [ ] Run all tests; expected all pass.

### Task 6: Phase 2 Preview and Documentation Gate

**Files:**
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/README.md`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/tools/preview_smoke.py`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/base.html`
- Modify: `HEW2026_v1.0_Chatbox_KimiK3.1Pro/app/templates/main/index.html`

- [ ] Add navigation to `描く` and account draft/listed counts without introducing live/admin/cancel/relist links.
- [ ] Extend preview smoke with actual duration selection and a generated valid PNG/layer save; assert draft image access and listing creation.
- [ ] Update README with drawing durations, tools, upload limits, listing durations, CLI initialization, and test commands actually used.
- [ ] Run `.venv/Scripts/python -m pytest -q`; expected zero failures.
- [ ] Run the real `npm run dev -- --host 127.0.0.1 --port 7100` smoke test and stop every child process before reporting completion.
