"""Configuration management using Pydantic"""

from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class AssetConfig(BaseModel):
    """Configuration for a single asset"""
    symbol: str
    max_weight: float = Field(ge=0.0, le=1.0, description="Maximum portfolio weight")
    min_weight: float = Field(ge=0.0, le=1.0, description="Minimum portfolio weight")
    is_stablecoin: bool = False


class RiskConfig(BaseModel):
    """Risk management configuration"""
    max_drawdown_pct: float = Field(default=0.25, ge=0.0, le=1.0, description="Max portfolio drawdown before kill switch")
    max_single_asset_weight: float = Field(default=0.60, ge=0.0, le=1.0)
    max_daily_turnover: float = Field(default=0.50, ge=0.0, le=1.0, description="Max daily portfolio turnover")
    turnover_mode: str = Field(default="scale", description="Turnover handling: 'scale' to scale down rebalance, 'skip' to skip")
    cooldown_minutes: int = Field(default=60, ge=0, description="Cooldown after regime change")
    min_rebalance_delta: float = Field(default=0.01, ge=0.0, le=1.0, description="Minimum portfolio turnover required to trigger rebalance (default 1%)")
    drawdown_risk_off_threshold: float = Field(default=0.15, ge=0.0, description="Drawdown % to trigger risk-off (hard override)")
    drawdown_severe_threshold: float = Field(default=0.25, ge=0.0, description="Severe drawdown threshold (force risk_off)")
    drawdown_recover_threshold: float = Field(default=0.10, ge=0.0, description="Drawdown % to allow recovery from risk_off")
    emergency_dd: float = Field(default=0.10, ge=0.0, le=1.0, description="Portfolio drawdown % to trigger emergency de-risking bypass (default 10%)")
    emergency_turnover_multiplier: float = Field(default=2.0, ge=1.0, description="Emergency turnover budget multiplier (default 2.0 = +200%)")
    emergency_min_stable_increase: float = Field(default=0.10, ge=0.0, le=1.0, description="Minimum stablecoin weight increase during emergency de-risk (default 10%)")
    volatility_threshold: float = Field(default=0.05, description="Rolling volatility threshold for risk-off")
    ma_periods: int = Field(default=200, ge=1, description="Moving average periods")
    allow_reenable: bool = Field(default=False, description="Allow trading to re-enable after kill-switch")
    
    # Regime state machine parameters
    regime_min_hold_hours: int = Field(default=6, ge=0, description="Minimum hours to hold current regime before switching")
    regime_enter_neutral_threshold: float = Field(default=0.75, ge=0.0, le=1.0, description="Score threshold to enter neutral from risk_on")
    regime_enter_risk_off_threshold: float = Field(default=0.45, ge=0.0, le=1.0, description="Score threshold to enter risk_off")
    regime_exit_risk_off_threshold: float = Field(default=0.65, ge=0.0, le=1.0, description="Score threshold to exit risk_off")
    regime_exit_neutral_threshold: float = Field(default=0.85, ge=0.0, le=1.0, description="Score threshold to exit neutral to risk_on")
    regime_confirmation_bars_risk_off: int = Field(default=3, ge=1, description="Consecutive bars required to switch to less risky regime")
    regime_confirmation_bars_risk_on: int = Field(default=6, ge=1, description="Consecutive bars required to switch to more risky regime")
    
    # Signal weights
    signal_weight_drawdown: float = Field(default=0.5, ge=0.0, le=1.0, description="Weight for drawdown signal in score calculation")
    signal_weight_ma: float = Field(default=0.3, ge=0.0, le=1.0, description="Weight for price below MA signal in score calculation")
    signal_weight_volatility: float = Field(default=0.2, ge=0.0, le=1.0, description="Weight for volatility signal in score calculation")


class RebalanceConfig(BaseModel):
    """Rebalancing configuration"""
    frequency_minutes: int = Field(default=60, ge=1, description="Rebalancing frequency")
    risk_off_stable_weight: float = Field(default=0.80, ge=0.0, le=1.0, description="Stablecoin weight in risk-off")
    risk_on_btc_weight: float = Field(default=0.50, ge=0.0, le=1.0)
    risk_on_eth_weight: float = Field(default=0.30, ge=0.0, le=1.0)
    dca_steps: int = Field(default=3, ge=1, description="Number of DCA steps when re-entering")
    contrarian_buy_threshold: float = Field(default=0.15, ge=0.0, description="Drawdown % to trigger contrarian buy")
    contrarian_buy_size: float = Field(default=0.05, ge=0.0, le=1.0, description="Size of contrarian buy as % of portfolio")


class NewsConfig(BaseModel):
    """News and LLM configuration"""
    enabled: bool = False
    llm_provider: str = "openai"  # openai, anthropic, or custom
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    max_llm_influence: float = Field(default=0.15, ge=0.0, le=1.0, description="Max regime score adjustment from LLM")
    news_sources: List[str] = Field(default_factory=lambda: ["coindesk", "cointelegraph"])
    fetch_interval_minutes: int = Field(default=60, ge=1)


class NewsDipConfig(BaseModel):
    """Alert-only news + dip strategy configuration"""
    enabled: bool = True
    symbols: List[str] = Field(default_factory=lambda: ["BTC", "ETH", "SOL", "ZEC"])
    quote: str = "USDT"
    news_sources: List[str] = Field(default_factory=lambda: ["coindesk", "cointelegraph"])
    news_window_minutes: int = Field(default=60, ge=1)
    poll_interval_seconds: int = Field(default=60, ge=10)
    dip_lookback_hours: int = Field(default=24, ge=1)
    dip_min_pct: float = Field(default=0.03, ge=0.0, description="Min dip from local high (e.g. 0.03 = 3%)")
    dip_max_pct: float = Field(default=0.08, ge=0.0, description="Max dip considered (deeper = too risky / skip)")
    volume_ratio_min: float = Field(default=0.8, ge=0.0, description="Current volume vs median ratio floor")
    late_move_pct: float = Field(default=0.05, ge=0.0, description="Skip if price already recovered this much from dip low")
    take_profit_pct: float = Field(default=0.04, ge=0.0)
    stop_loss_pct: float = Field(default=0.025, ge=0.0)
    time_stop_hours: int = Field(default=24, ge=1)
    risk_per_alert_pct: float = Field(default=0.01, ge=0.0, le=1.0, description="Suggested size as % of bank")
    bank_usdt: float = Field(default=10000.0, ge=0.0, description="Reference bank for size suggestions")
    signal_cooldown_minutes: int = Field(default=120, ge=0, description="Min time between alerts per symbol")
    require_high_confidence: bool = True
    ohlcv_timeframe: str = "1h"
    ohlcv_limit: int = Field(default=48, ge=10)
    # Bear / treasury-sell leg
    enable_bear_alerts: bool = True
    bear_late_move_pct: float = Field(
        default=0.04,
        ge=0.0,
        description="Skip bear alert if already down this much in 24h (likely priced in)",
    )


class SpotGridConfig(BaseModel):
    """Paper spot-grid parameters."""
    enabled: bool = True
    symbol: str = "BTC"
    levels: int = Field(default=10, ge=4, le=40)
    range_pct: float = Field(default=0.04, gt=0.0, description="Total band width around mid, e.g. 0.04 = ±2%")
    order_size_usdt: float = Field(default=50.0, gt=0.0)
    fee_bps: float = Field(default=10.0, ge=0.0)
    bank_usdt: float = Field(default=1000.0, ge=0.0)
    recenter_on_break: bool = True


class StrategyTestConfig(BaseModel):
    """Paper-test harness for news / rebalance / grid."""
    enabled: bool = True
    # news | rebalance | grid | both | all
    mode: str = Field(default="both")
    auto_paper: bool = False
    paper_bank_usdt: float = Field(default=5000.0, ge=0.0)
    max_open_positions: int = Field(default=5, ge=1)
    rebalance_paper_fraction: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Paper-trade this fraction of suggested rebalance notional",
    )

    @field_validator("mode")
    @classmethod
    def validate_strategy_mode(cls, v: str) -> str:
        if v not in ("news", "rebalance", "grid", "both", "all"):
            raise ValueError("strategy_test.mode must be news|rebalance|grid|both|all")
        return v


class CycleRebalanceConfig(BaseModel):
    """BTC/Alt season → phase allocation targets for dry-run rebalance."""
    enabled: bool = True
    alt_index_btc_max: float = Field(default=25.0, ge=0.0, le=100.0)
    alt_index_alt_min: float = Field(default=75.0, ge=0.0, le=100.0)
    btc_d_lookback_days: int = Field(default=30, ge=1)
    btc_d_flat_band_pct: float = Field(default=0.3, ge=0.0)
    cache_ttl_hours: float = Field(default=12.0, ge=0.5)
    min_action_usdt: float = Field(default=20.0, ge=0.0)
    no_refill: List[str] = Field(default_factory=lambda: ["AAVE", "LINK", "FIL", "XRP"])
    thresholds_pct: Dict[str, float] = Field(default_factory=lambda: {
        "BTC": 15, "ETH": 15, "BNB": 15, "USDT": 15,
        "SOL": 25, "XRP": 25, "LINK": 25, "AAVE": 25, "ZEC": 25, "FIL": 25, "PAXG": 20,
    })
    phases: Dict[str, Dict[str, float]] = Field(default_factory=lambda: {
        "btc_season": {
            "BTC": 35, "ETH": 22, "SOL": 5, "BNB": 4, "XRP": 2,
            "LINK": 2, "AAVE": 2, "ZEC": 2, "FIL": 1, "PAXG": 7, "USDT": 18,
        },
        "neutral": {
            "BTC": 28, "ETH": 20, "SOL": 8, "BNB": 6, "XRP": 3,
            "LINK": 4, "AAVE": 4, "ZEC": 4, "FIL": 2, "PAXG": 6, "USDT": 15,
        },
        "alt_season": {
            "BTC": 22, "ETH": 18, "SOL": 12, "BNB": 8, "XRP": 4,
            "LINK": 5, "AAVE": 5, "ZEC": 5, "FIL": 3, "PAXG": 5, "USDT": 13,
        },
    })


class ExchangeConfig(BaseModel):
    """Exchange configuration"""
    name: str = "mock"
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    sandbox: bool = True
    dry_run: bool = True  # Safety: require explicit enable for live trading


class Settings(BaseSettings):
    """Main application settings"""
    # Mode
    mode: str = Field(default="backtest", description="backtest, paper, live, or alerts")
    
    # Data
    data_file: Optional[Path] = None
    data_timeframe: str = "5m"
    rebalance_timeframe: str = "1h"  # Aggregate to this for rebalancing
    
    # Assets
    assets: List[AssetConfig] = Field(default_factory=lambda: [
        AssetConfig(symbol="BTC", max_weight=0.60, min_weight=0.0),
        AssetConfig(symbol="ETH", max_weight=0.40, min_weight=0.0),
        AssetConfig(symbol="USDT", max_weight=1.0, min_weight=0.0, is_stablecoin=True),
    ])
    
    # Risk
    risk: RiskConfig = Field(default_factory=RiskConfig)
    
    # Rebalancing
    rebalance: RebalanceConfig = Field(default_factory=RebalanceConfig)
    
    # News
    news: NewsConfig = Field(default_factory=NewsConfig)

    # News + dip alerts
    news_dip: NewsDipConfig = Field(default_factory=NewsDipConfig)

    # Spot grid (paper)
    spot_grid: SpotGridConfig = Field(default_factory=SpotGridConfig)

    # Paper strategy test (news and/or rebalance)
    strategy_test: StrategyTestConfig = Field(default_factory=StrategyTestConfig)

    # Cycle-aware rebalance (BTC/Alt season targets)
    cycle_rebalance: CycleRebalanceConfig = Field(default_factory=CycleRebalanceConfig)
    
    # Exchange
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    
    # Output
    output_dir: Path = Field(default=Path("out"), description="Output directory for results")
    
    # Initial portfolio
    initial_balance: float = Field(default=10000.0, ge=0.0, description="Initial portfolio value in USDT")
    
    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ['backtest', 'paper', 'live', 'alerts']:
            raise ValueError("mode must be 'backtest', 'paper', 'live', or 'alerts'")
        return v
    
    @field_validator('assets')
    @classmethod
    def validate_assets(cls, v: List[AssetConfig]) -> List[AssetConfig]:
        """Ensure at least one stablecoin exists (not required for alerts-only configs)."""
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


def load_config(config_path: Optional[Path] = None) -> Settings:
    """Load configuration from file and environment variables"""
    if config_path and config_path.exists():
        try:
            import yaml
            with open(config_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
            
            # Flatten nested structure if needed
            # YAML has nested structure, but Settings expects flat with nested models
            if 'data' in yaml_data:
                if yaml_data['data'].get('file'):
                    yaml_data['data_file'] = Path(yaml_data['data']['file']) if yaml_data['data']['file'] else None
                yaml_data['data_timeframe'] = yaml_data['data'].get('timeframe', '5m')
                yaml_data['rebalance_timeframe'] = yaml_data['data'].get('rebalance_timeframe', '1h')
                del yaml_data['data']
            
            # Handle nested risk, rebalance, news, exchange configs
            # Pydantic will handle these automatically if they match the model structure
            
            # Convert YAML to dict and create Settings
            return Settings(**yaml_data)
        except ImportError:
            print("Warning: PyYAML not installed. Install with: pip install pyyaml")
            print("Using default configuration.")
            return Settings()
        except Exception as e:
            print(f"Error loading config from {config_path}: {e}")
            print("Using default configuration.")
            return Settings()
    return Settings()

