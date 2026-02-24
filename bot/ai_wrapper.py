"""
Wraps trading logic with AI-based position and signal evaluation
"""
from ai_engine.model import AIModel
from ai_engine.sentiment import SentimentAnalyzer
from ai_engine.features import FeatureBuilder

class SmartAIBot:

    def __init__(self):
        self.model = AIModel()
        self.sentiment = SentimentAnalyzer()
        self.features = FeatureBuilder()

    def compute_signals(self, price_df, symbol):
        """
        Returns an AI-enhanced buy/sell/hold signal.
        """

        # Traditional EMA Logic
        price_df = self.features.add_ema(price_df)
        last = price_df.iloc[-1]
        prev = price_df.iloc[-2]

        ema_signal = 1 if last["ema_fast"] > last["ema_slow"] else -1

        # AI Prediction
        ai_signal = self.model.predict(price_df)

        # News Sentiment
        sentiment_score = self.sentiment.score(symbol)

        # TRIPLE VOTE SYSTEM
        total = ema_signal + ai_signal + sentiment_score

        if total >= 2:
            return "buy"
        elif total <= -2:
            return "sell"
        return "hold"
