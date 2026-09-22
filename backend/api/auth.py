"""
VinaLex — API Routes: Xác thực người dùng (Auth)

Tuân thủ README.md §5: backend/api/ = routes (users)
Endpoint prefix: /api/v1/auth (đăng ký trong main.py)

Lưu trữ: PostgreSQL (tài khoản người dùng) — KHÔNG dùng Redis cho auth

Bảo mật (nâng cấp):
  - Mật khẩu: bcrypt (passlib) thay cho sha256 + salt cố định
  - Token: JWT chuẩn (python-jose) với claims sub, exp, iat
  - Middleware: get_current_user dependency tái sử dụng ở các route khác
"""

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.postgres import get_db
from backend.models.procedure import UserModel, UserProcedureModel, ProcedureModel
from backend.models.schemas import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse,
    UserProcedureResponse, SaveUserProcedureRequest,
)
from backend.core.config import settings

# ── Thư viện bảo mật ──
try:
    import bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False

try:
    from jose import JWTError, jwt
    _JOSE_AVAILABLE = True
except ImportError:
    _JOSE_AVAILABLE = False

_CRYPTO_AVAILABLE = _BCRYPT_AVAILABLE and _JOSE_AVAILABLE

router = APIRouter()

# ── JWT config ──
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 ngày

# ── OAuth2 scheme (dùng để bảo vệ route cần auth) ──
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ──────────────────────────────────────────────────────────────────────
# ── Hàm utility bảo mật ──
# ──────────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """
    Hash mật khẩu bằng bcrypt.
    Fallback sang sha256 nếu bcrypt chưa được cài đặt.
    """
    if _BCRYPT_AVAILABLE:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    # Fallback cũ — vẫn hoạt động nhưng kém bảo mật hơn
    import hashlib
    salt = settings.SECRET_KEY[:16]
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Kiểm tra mật khẩu plaintext so với hash đã lưu.
    Hỗ trợ cả bcrypt lẫn sha256 (để tương thích dữ liệu cũ).
    """
    if _BCRYPT_AVAILABLE and (hashed_password.startswith("$2a$") or hashed_password.startswith("$2b$") or hashed_password.startswith("$2y$")):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False

    # Tương thích ngược với hash sha256 cũ
    import hashlib
    old_salt = "vinalex_salt_2024"
    if hashlib.sha256(f"{old_salt}{plain_password}".encode()).hexdigest() == hashed_password:
        return True
    salt = settings.SECRET_KEY[:16]
    return hashlib.sha256(f"{salt}{plain_password}".encode()).hexdigest() == hashed_password


def _create_access_token(user_id: int, email: str) -> str:
    """
    Tạo JWT access token với claims chuẩn.

    Claims:
      sub   — email người dùng (subject)
      uid   — user_id
      exp   — thời điểm hết hạn (UTC)
      iat   — thời điểm phát hành (UTC)
    """
    if not _CRYPTO_AVAILABLE:
        # Fallback khi python-jose chưa cài
        import secrets
        return f"token_{user_id}_{secrets.token_urlsafe(32)}"

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "uid": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> Optional[dict]:
    """
    Giải mã và xác thực JWT token.

    Returns:
        Dict payload nếu token hợp lệ và chưa hết hạn, None nếu không hợp lệ.
    """
    if not _CRYPTO_AVAILABLE:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ──────────────────────────────────────────────────────────────────────
# ── Dependency: get_current_user — bảo vệ các route cần auth ──
# ──────────────────────────────────────────────────────────────────────

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    """
    FastAPI dependency: giải mã JWT token và trả về UserModel đang đăng nhập.

    Sử dụng:
        @router.get("/protected-route")
        async def protected(current_user: UserModel = Depends(get_current_user)):
            ...

    Raises:
        HTTP 401 nếu token thiếu, hết hạn hoặc user không tồn tại.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    payload = _decode_token(token)
    if payload is None:
        raise credentials_exception

    email: Optional[str] = payload.get("sub")
    if not email:
        raise credentials_exception

    # Tra cứu user từ database
    try:
        result = await db.execute(
            select(UserModel).where(
                UserModel.email == email,
                UserModel.is_active == True,
            )
        )
        user = result.scalar_one_or_none()
    except Exception:
        raise credentials_exception

    if user is None:
        raise credentials_exception

    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserModel]:
    """
    Phiên bản không bắt buộc của get_current_user.
    Trả về None nếu chưa đăng nhập (không raise exception).
    Dùng cho các route vừa phục vụ khách vừa phục vụ user đã đăng nhập.
    """
    if not token:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None


# ──────────────────────────────────────────────────────────────────────
# ── API Endpoints ──
# ──────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Đăng ký tài khoản mới.

    - Kiểm tra email đã tồn tại chưa (trả về 409 Conflict nếu trùng)
    - Hash mật khẩu bằng bcrypt trước khi lưu
    """
    # Kiểm tra email đã tồn tại chưa
    result = await db.execute(
        select(UserModel).where(UserModel.email == request.email)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được sử dụng",
        )

    # Tạo tài khoản mới với mật khẩu đã hash bằng bcrypt
    new_user = UserModel(
        name=request.name,
        email=request.email,
        hashed_password=_hash_password(request.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Đăng nhập và nhận JWT access token.

    - Xác minh email + mật khẩu (bcrypt verify)
    - Trả về JWT token với hạn sử dụng 7 ngày
    """
    result = await db.execute(
        select(UserModel).where(
            UserModel.email == request.email,
            UserModel.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not _verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    access_token = _create_access_token(user.id, user.email)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    """
    Lấy thông tin tài khoản đang đăng nhập.
    Yêu cầu JWT token hợp lệ trong header: Authorization: Bearer <token>
    """
    return UserResponse.model_validate(current_user)


@router.get("/me/procedures", response_model=List[UserProcedureResponse])
async def get_my_procedures(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy danh sách hồ sơ thủ tục người dùng đang theo dõi từ CSDL.
    """
    stmt = (
        select(UserProcedureModel, ProcedureModel.title)
        .join(ProcedureModel, UserProcedureModel.procedure_id == ProcedureModel.id, isouter=True)
        .where(UserProcedureModel.user_id == current_user.id)
        .order_by(UserProcedureModel.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for user_proc, proc_title in rows:
        items.append(
            UserProcedureResponse(
                id=user_proc.id,
                procedure_id=user_proc.procedure_id,
                procedure_title=proc_title or "Thủ tục hành chính",
                progress=user_proc.progress,
                status=user_proc.status,
                due_date=user_proc.due_date,
                created_at=user_proc.created_at,
            )
        )
    return items


@router.post("/me/procedures", response_model=UserProcedureResponse)
async def save_my_procedure(
    request: SaveUserProcedureRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lưu/theo dõi một thủ tục hành chính vào hồ sơ cá nhân.
    """
    p_res = await db.execute(select(ProcedureModel).where(ProcedureModel.id == request.procedure_id))
    proc = p_res.scalar_one_or_none()
    if not proc:
        raise HTTPException(status_code=404, detail="Thủ tục không tồn tại")

    existing_res = await db.execute(
        select(UserProcedureModel).where(
            UserProcedureModel.user_id == current_user.id,
            UserProcedureModel.procedure_id == request.procedure_id,
        )
    )
    user_proc = existing_res.scalar_one_or_none()
    if user_proc:
        if request.notes is not None:
            user_proc.notes = request.notes
        if request.due_date is not None:
            user_proc.due_date = request.due_date
        if request.status:
            user_proc.status = request.status
        if request.progress is not None:
            user_proc.progress = request.progress
    else:
        user_proc = UserProcedureModel(
            user_id=current_user.id,
            procedure_id=request.procedure_id,
            progress=request.progress or 0,
            status=request.status or "pending",
            notes=request.notes,
            due_date=request.due_date,
        )
        db.add(user_proc)

    await db.commit()
    await db.refresh(user_proc)

    return UserProcedureResponse(
        id=user_proc.id,
        procedure_id=user_proc.procedure_id,
        procedure_title=proc.title,
        progress=user_proc.progress,
        status=user_proc.status,
        due_date=user_proc.due_date,
        created_at=user_proc.created_at,
    )


@router.delete("/me/procedures/{user_proc_id}")
async def delete_my_procedure(
    user_proc_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Xóa thủ tục khỏi danh sách hồ sơ theo dõi của người dùng.
    """
    stmt = select(UserProcedureModel).where(
        UserProcedureModel.id == user_proc_id,
        UserProcedureModel.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    user_proc = res.scalar_one_or_none()
    if not user_proc:
        raise HTTPException(status_code=404, detail="Hồ sơ không tồn tại hoặc không thuộc quyền sở hữu")

    await db.delete(user_proc)
    await db.commit()
    return {"message": "Đã xóa hồ sơ thành công", "id": user_proc_id}

