from __future__ import annotations

"""
Raptech Autotrade CLI — Configuration & Profile Storage.
Supports multi-profile loading, atomic writes, and parameter validation.
"""

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.secure_store import decrypt, encrypt

logger = get_logger("config")

PROFILES_DIR = Path("data/profiles")
SETTINGS_FILE = Path("data/settings.json")


@dataclass
class RiskSettings:
    fixed_lot: float = 0.01
    risk_percent: float = 1.0
    sizing_mode: str = "fixed_lot"  # fixed_lot | risk_percent
    virtual_sl_points: int = 0      # 0 = Otomatis mengikuti strategi kustom
    virtual_tp_points: int = 0      # 0 = Otomatis mengikuti strategi kustom
    use_server_sl: bool = False  # Layering: broker-side hard SL
    server_sl_points: int = 0  # 0 = fallback to virtual_sl_points
    trailing_enabled: bool = True
    trail_start_points: int = 0     # 0 = Otomatis mengikuti strategi
    trail_step_points: int = 0
    max_daily_loss: float = 50.0
    max_open_positions: int = 3
    max_drawdown_percent: float = 5.0
    min_margin_level: float = 500.0
    max_symbol_exposure_lots: float = 1.0


@dataclass
class AccountProfile:
    profile_name: str = "Default"
    backend: str = "native"  # native | mcp | simulation
    trading_mode: str = "demo"  # real | demo | simulasi
    login: int = 0
    password: str = ""
    server: str = "Exness-MT5Trial"
    path: str = ""
    mcp_url: str = "http://127.0.0.1:8000/mcp"
    mcp_api_key: str = ""
    symbols: List[str] = field(default_factory=list)
    timeframe: str = ""
    strategy: str = ""
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    allow_hedging: bool = False
    close_on_opposite_signal: bool = True
    risk: RiskSettings = field(default_factory=RiskSettings)
    auto_start: bool = False

    def to_dict(self, encrypt_password: bool = True) -> Dict[str, Any]:
        """Serialize profile strictly to account credentials & broker connection info."""
        d = {
            "profile_name": self.profile_name,
            "backend": self.backend,
            "trading_mode": self.trading_mode,
            "login": self.login,
            "password": encrypt(self.password) if (encrypt_password and self.password) else self.password,
            "server": self.server,
            "path": self.path,
            "mcp_url": self.mcp_url,
            "mcp_api_key": encrypt(self.mcp_api_key) if (encrypt_password and self.mcp_api_key) else self.mcp_api_key,
        }
        if self.symbols:
            d["symbols"] = self.symbols
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AccountProfile:
        d = dict(data)
        if "password" in d:
            d["password"] = decrypt(d["password"])
        if "mcp_api_key" in d:
            d["mcp_api_key"] = decrypt(d["mcp_api_key"])
        
        # Normalize trading_mode
        t_mode = str(d.get("trading_mode", "")).strip().lower()
        backend_val = str(d.get("backend", "native")).strip().lower()
        if not t_mode:
            if backend_val in ("simulation", "simulasi"):
                t_mode = "simulasi"
            elif "real" in str(d.get("server", "")).lower():
                t_mode = "real"
            else:
                t_mode = "demo"
        elif t_mode == "simulation":
            t_mode = "simulasi"
        d["trading_mode"] = t_mode

        risk_raw = d.pop("risk", {})
        valid_risk_keys = RiskSettings.__dataclass_fields__.keys()
        clean_risk = {k: v for k, v in risk_raw.items() if k in valid_risk_keys} if isinstance(risk_raw, dict) else {}
        risk = RiskSettings(**clean_risk)
        valid_cls_keys = cls.__dataclass_fields__.keys()
        clean_d = {k: v for k, v in d.items() if k in valid_cls_keys}
        return cls(**clean_d, risk=risk)


def atomic_write_json(file_path: Path, data: Any) -> None:
    """Safely write JSON file atomically via a temporary file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_name = tempfile.mkstemp(dir=file_path.parent, prefix="cfg_", suffix=".tmp")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_name, file_path)
    except Exception as e:
        if os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except Exception:
                pass
        raise e


def list_profiles() -> List[str]:
    """Return all profile names found in data/profiles/."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profiles = []
    for f in PROFILES_DIR.glob("*.json"):
        profiles.append(f.stem)
    return sorted(profiles)


def load_profile(name_or_path: Optional[str] = None) -> AccountProfile:
    """Load profile by name or file path. If None, load default or first available."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    
    target_path: Optional[Path] = None
    if name_or_path:
        p = Path(name_or_path)
        if p.exists() and p.is_file():
            target_path = p
        else:
            cand = PROFILES_DIR / f"{name_or_path}.json"
            if cand.exists():
                target_path = cand

    if not target_path:
        default_candidate = PROFILES_DIR / "default.json"
        if default_candidate.exists():
            target_path = default_candidate
        else:
            all_profiles = list_profiles()
            if all_profiles:
                target_path = PROFILES_DIR / f"{all_profiles[0]}.json"
            else:
                # Create default profile
                default_p = AccountProfile(profile_name="default")
                save_profile(default_p)
                return default_p

    try:
        content = json.loads(target_path.read_text(encoding="utf-8"))
        return AccountProfile.from_dict(content)
    except Exception as exc:
        logger.error(f"Gagal memuat profil {target_path}: {exc}")
        return AccountProfile(profile_name="Fallback")


def save_profile(profile: AccountProfile, name: Optional[str] = None) -> Path:
    """Save profile to data/profiles/<name>.json."""
    prof_name = name or profile.profile_name or "default"
    clean_name = "".join(c for c in prof_name if c.isalnum() or c in ("-", "_")).strip()
    if not clean_name:
        clean_name = "profile_1"
    
    file_path = PROFILES_DIR / f"{clean_name}.json"
    atomic_write_json(file_path, profile.to_dict(encrypt_password=True))
    logger.info(f"Profil berhasil disimpan: {file_path}")
    return file_path
