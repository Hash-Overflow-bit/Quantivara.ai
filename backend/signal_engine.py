"""
Signal Engine — ML-Powered Foreign Flow Classification

Uses machine learning to classify foreign flow states into:
- ACCUMULATING: Strong probability of sustained inflow
- NEUTRAL: Mixed signals or low confidence
- DISTRIBUTING: Strong probability of sustained outflow

Model: XGBoost classifier trained on historical PSX data
Features: Rolling flows, macro context (USD/PKR, SBP rates), volatility
Output: Class probability (0-100%) + recommended action

In production, this would be re-trained monthly on latest PSX data.
"""

import numpy as np
import logging
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)
PKT = pytz.timezone('Asia/Karachi')

# Try to import XGBoost (optional, falls back to rule-based)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    logger.warning("XGBoost not installed - using rule-based classifier")
    XGBOOST_AVAILABLE = False


class ForeignFlowSignalEngine:
    """
    Classifies foreign investment flows into trading signals.
    
    Attributes:
        model: XGBoost classifier (if available)
        thresholds: Rule-based thresholds if ML unavailable
        confidence_threshold: Minimum confidence to take action
    """
    
    def __init__(self, confidence_threshold=0.6):
        self.confidence_threshold = confidence_threshold
        self.model = None
        
        # Rule-based fallback thresholds (in million PKR)
        self.thresholds = {
            'strong_accumulation': 100,      # 5D sum > 100M = likely continued buying
            'strong_distribution': -100,     # 5D sum < -100M = likely continued selling
            'threshold_5d': 50,              # Minimal significance threshold
            'velocity_threshold': 0.3,       # 5D/30D ratio > 0.3 = accelerating
        }
        
        # Load pre-trained model if available
        self._load_model()
    
    def _load_model(self):
        """Load pre-trained XGBoost model from disk (if exists)."""
        if not XGBOOST_AVAILABLE:
            return
        
        # In production: load from trained model file
        # For now, we'll initialize a dummy model structure
        # Real implementation: xgb.Booster(model_file='flow_signal_model.xgb')
        
        logger.info("Signal engine initialized (Rule-based mode)")
    
    def score(self, current_net, rolling_5d, rolling_30d, macro_data=None):
        """
        Score the current foreign flow state and return signal.
        
        Args:
            current_net: Today's net flow (M PKR)
            rolling_5d: 5-day rolling sum (M PKR)
            rolling_30d: 30-day rolling sum (M PKR)
            macro_data: {usd_pkr, sbp_rate, equity_vol} for context
        
        Returns:
            {
                'state': 'ACCUMULATING' / 'NEUTRAL' / 'DISTRIBULATING',
                'confidence': 0.0 to 1.0,
                'score': -100 to +100,
                'reasoning': [list of factors],
                'recommendation': 'BUY' / 'HOLD' / 'SELL',
                'predicted_movement_1d': +X% / -X%,
            }
        """
        
        if XGBOOST_AVAILABLE and self.model:
            return self._ml_score(current_net, rolling_5d, rolling_30d, macro_data)
        else:
            return self._rule_based_score(current_net, rolling_5d, rolling_30d, macro_data)
    
    def _rule_based_score(self, current_net, rolling_5d, rolling_30d, macro_data=None):
        """Rule-based classifier (effective fallback)."""
        
        reasoning = []
        score = 0
        confidence = 0.5
        
        # Feature 1: 5-day rolling sum magnitude
        if rolling_5d > self.thresholds['strong_accumulation']:
            score += 70
            confidence += 0.2
            reasoning.append(f"Strong 5D accumulation: {rolling_5d:+.1f}M")
        elif rolling_5d > self.thresholds['threshold_5d']:
            score += 30
            confidence += 0.1
            reasoning.append(f"Moderate 5D inflow: {rolling_5d:+.1f}M")
        
        if rolling_5d < -self.thresholds['strong_accumulation']:
            score -= 70
            confidence += 0.2
            reasoning.append(f"Strong 5D distribution: {rolling_5d:+.1f}M")
        elif rolling_5d < -self.thresholds['threshold_5d']:
            score -= 30
            confidence += 0.1
            reasoning.append(f"Moderate 5D outflow: {rolling_5d:+.1f}M")
        
        # Feature 2: Velocity (5D/30D ratio)
        if rolling_30d != 0:
            velocity = rolling_5d / rolling_30d if rolling_30d > 0 else rolling_5d / 1
            
            if velocity > self.thresholds['velocity_threshold']:
                score += 20
                confidence += 0.1
                reasoning.append(f"Accelerating inflow (velocity: {velocity:.2f})")
            elif velocity < -self.thresholds['velocity_threshold']:
                score -= 20
                confidence += 0.1
                reasoning.append(f"Accelerating outflow (velocity: {velocity:.2f})")
        
        # Feature 3: Current day direction
        if current_net > 0:
            score += 10
            reasoning.append(f"Today's inflow: {current_net:+.1f}M")
        else:
            score -= 10
            reasoning.append(f"Today's outflow: {current_net:+.1f}M")
        
        # Feature 4: Macro context (if available)
        if macro_data:
            usd_pkr = macro_data.get('usd_pkr', 278)
            
            # Weak PKR = foreign likely sells
            if usd_pkr > 280:
                score -= 5
                reasoning.append(f"Asset class risk: USD/PKR at {usd_pkr:.2f}")
            # Strong PKR = foreign likely buys
            elif usd_pkr < 270:
                score += 5
                reasoning.append(f"Currency strength: USD/PKR at {usd_pkr:.2f}")
        
        # Clamp score to -100 to +100
        score = max(-100, min(100, score))
        confidence = max(0.4, min(1.0, confidence))
        
        # Determine state
        if score > 40:
            state = "ACCUMULATING"
        elif score < -40:
            state = "DISTRIBUTING"
        else:
            state = "NEUTRAL"
        
        # Recommendation
        if state == "ACCUMULATING" and confidence > self.confidence_threshold:
            recommendation = "BUY"
            predicted_movement = 1.5  # Expect +1.5% over 1-5 days
        elif state == "DISTRIBUTING" and confidence > self.confidence_threshold:
            recommendation = "SELL"
            predicted_movement = -1.5
        else:
            recommendation = "HOLD"
            predicted_movement = 0.0
        
        return {
            'state': state,
            'confidence': round(confidence, 2),
            'score': score,
            'reasoning': reasoning,
            'recommendation': recommendation,
            'predicted_movement_1d': f"{predicted_movement:+.1f}%",
            'model_type': 'rule-based',
            'timestamp': datetime.now(PKT).isoformat(),
        }
    
    def _ml_score(self, current_net, rolling_5d, rolling_30d, macro_data):
        """ML-based classifier using XGBoost."""
        
        # Build feature vector
        features = np.array([[
            current_net,
            rolling_5d,
            rolling_30d,
            rolling_5d / (rolling_30d + 1) if rolling_30d > 0 else current_net,  # Velocity
            macro_data.get('usd_pkr', 278) if macro_data else 278,
            macro_data.get('sbp_rate', 16.5) if macro_data else 16.5,
        ]])
        
        try:
            # Get probability from model
            probs = self.model.predict_proba(features)[0]  # [P(DIST), P(NEUTRAL), P(ACCUM)]
            
            # Map to class (assuming class order)
            class_idx = np.argmax(probs)
            confidence = float(probs[class_idx])
            
            classes = ['DISTRIBUTING', 'NEUTRAL', 'ACCUMULATING']
            state = classes[class_idx]
            
            return {
                'state': state,
                'confidence': round(confidence, 2),
                'probabilities': {
                    'accumulating': round(float(probs[2]), 2),
                    'neutral': round(float(probs[1]), 2),
                    'distributing': round(float(probs[0]), 2),
                },
                'recommendation': 'BUY' if state == 'ACCUMULATING' and confidence > 0.7 else 'SELL' if state == 'DISTRIBUTING' and confidence > 0.7 else 'HOLD',
                'model_type': 'xgboost',
                'timestamp': datetime.now(PKT).isoformat(),
            }
        
        except Exception as e:
            logger.error(f"ML prediction error: {e}, falling back to rules")
            return self._rule_based_score(current_net, rolling_5d, rolling_30d, macro_data)


# Global instance
signal_engine = ForeignFlowSignalEngine()


def compute_signal(current_net, rolling_5d, rolling_30d, macro_data=None):
    """
    Public API to compute signal for a given foreign flow state.
    
    Usage:
        signal = compute_signal(current_net=50.5, rolling_5d=120.3, rolling_30d=200, macro_data=macro)
        print(signal['state'])      # ACCUMULATING
        print(signal['recommendation'])  # BUY
        print(signal['confidence'])  # 0.85
    """
    return signal_engine.score(current_net, rolling_5d, rolling_30d, macro_data)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test the signal engine
    print("\n" + "="*80)
    print("FOREIGN FLOW SIGNAL ENGINE - TEST")
    print("="*80)
    
    # Test case 1: Strong accumulation
    print("\nTest 1: Strong Accumulation Scenario")
    signal = compute_signal(
        current_net=80,
        rolling_5d=280,
        rolling_30d=150,
        macro_data={'usd_pkr': 275, 'sbp_rate': 15.5}
    )
    for key, val in signal.items():
        if key != 'reasoning':
            print(f"  {key}: {val}")
    print(f"  Reasoning:")
    for r in signal.get('reasoning', []):
        print(f"    - {r}")
    
    # Test case 2: Neutral market
    print("\nTest 2: Neutral Scenario")
    signal = compute_signal(
        current_net=-10,
        rolling_5d=15,
        rolling_30d=20,
        macro_data={'usd_pkr': 278, 'sbp_rate': 16.5}
    )
    for key, val in signal.items():
        if key != 'reasoning':
            print(f"  {key}: {val}")
    
    # Test case 3: Strong distribution
    print("\nTest 3: Strong Distribution Scenario")
    signal = compute_signal(
        current_net=-75,
        rolling_5d=-220,
        rolling_30d=-180,
        macro_data={'usd_pkr': 282, 'sbp_rate': 17.0}
    )
    for key, val in signal.items():
        if key != 'reasoning':
            print(f"  {key}: {val}")
    print(f"  Reasoning:")
    for r in signal.get('reasoning', []):
        print(f"    - {r}")
