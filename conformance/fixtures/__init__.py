"""
Conformance Fixtures (Section 13).

Each fixture defines positive and negative scenarios for specific
adversarial patterns that A2ASTC must detect.
"""

from .capability_laundering import FIXTURE_ID as CAPABILITY_LAUNDERING_ID
from .emergent_collusion import FIXTURE_ID as EMERGENT_COLLUSION_ID
from .deceptive_cascade import FIXTURE_ID as DECEPTIVE_CASCADE_ID
from .sidechannel_timing import FIXTURE_ID as SIDECHANNEL_TIMING_ID
from .sidechannel_length import FIXTURE_ID as SIDECHANNEL_LENGTH_ID
from .steganography_metadata import FIXTURE_ID as STEGANOGRAPHY_METADATA_ID
from .privilege_aggregation import FIXTURE_ID as PRIVILEGE_AGGREGATION_ID
from .identity_multiplication import FIXTURE_ID as IDENTITY_MULTIPLICATION_ID
from .prompt_injection_cascade import FIXTURE_ID as PROMPT_INJECTION_CASCADE_ID
from .coalition_against_third import FIXTURE_ID as COALITION_AGAINST_THIRD_ID
from .convergent_vocabulary import FIXTURE_ID as CONVERGENT_VOCABULARY_ID
from .throttle_evasion import FIXTURE_ID as THROTTLE_EVASION_ID
from .isolation_evasion import FIXTURE_ID as ISOLATION_EVASION_ID
from .manifest_desync import FIXTURE_ID as MANIFEST_DESYNC_ID
from .trail_tamper import FIXTURE_ID as TRAIL_TAMPER_ID

ALL_FIXTURE_IDS = [
    CAPABILITY_LAUNDERING_ID,
    EMERGENT_COLLUSION_ID,
    DECEPTIVE_CASCADE_ID,
    SIDECHANNEL_TIMING_ID,
    SIDECHANNEL_LENGTH_ID,
    STEGANOGRAPHY_METADATA_ID,
    PRIVILEGE_AGGREGATION_ID,
    IDENTITY_MULTIPLICATION_ID,
    PROMPT_INJECTION_CASCADE_ID,
    COALITION_AGAINST_THIRD_ID,
    CONVERGENT_VOCABULARY_ID,
    THROTTLE_EVASION_ID,
    ISOLATION_EVASION_ID,
    MANIFEST_DESYNC_ID,
    TRAIL_TAMPER_ID,
]
