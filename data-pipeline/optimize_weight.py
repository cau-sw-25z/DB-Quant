"""
자산 배분 최적화 모듈 - Inverse Volatility 방식
이슈: DB-06 / 선행: DB-05 (annual_volatility 계산 완료)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

