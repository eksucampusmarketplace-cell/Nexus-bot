import os
import logging
import asyncio
import joblib
from db.client import db

logger = logging.getLogger(__name__)
MODEL_PATH = 'bot/ml/spam_model.pkl'

class SpamClassifier:
    def __init__(self):
        self.model = None
        self.is_trained = False

    async def load(self) -> bool:
        """Load pickled model from MODEL_PATH if it exists."""
        try:
            if os.path.exists(MODEL_PATH):
                # Run in thread pool as joblib.load can be blocking
                self.model = await asyncio.to_thread(joblib.load, MODEL_PATH)
                self.is_trained = True
                return True
        except Exception as e:
            logger.error(f"Failed to load spam model: {e}")
        return False

    def predict(self, text: str) -> dict:
        """Returns: {label: 'spam'|'ham', confidence: float, is_trained: bool}"""
        if not self.is_trained or self.model is None or not text:
            return {'label': 'unknown', 'confidence': 0.0, 'is_trained': self.is_trained}
            
        try:
            # Predict
            probs = self.model.predict_proba([text])[0]
            classes = self.model.classes_
            
            # Find the max probability
            max_idx = probs.argmax()
            label = classes[max_idx]
            confidence = float(probs[max_idx])
            
            return {
                'label': label,
                'confidence': confidence,
                'is_trained': True
            }
        except Exception as e:
            logger.debug(f"Prediction failed: {e}")
            return {'label': 'unknown', 'confidence': 0.0, 'is_trained': self.is_trained}

    async def train(self, min_samples: int = 500) -> dict:
        """
        Load labelled data from spam_signals table and train a model.
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import Pipeline
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import classification_report, accuracy_score
            import numpy as np

            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT message_text, label FROM spam_signals WHERE label IN ('spam', 'ham') AND message_text IS NOT NULL"
                )
            
            if len(rows) < min_samples:
                return {
                    'trained': False, 
                    'samples': len(rows), 
                    'error': f"Not enough samples to train. Need at least {min_samples}."
                }

            texts = [r['message_text'] for r in rows]
            labels = [r['label'] for r in rows]

            # Run training in a separate thread to avoid blocking the event loop
            def _train_in_thread():
                X_train, X_test, y_train, y_test = train_test_split(
                    texts, labels, test_size=0.2, random_state=42, stratify=labels
                )

                pipeline = Pipeline([
                    ('tfidf', TfidfVectorizer(
                        max_features=10000, 
                        ngram_range=(1, 2),
                        min_df=2, 
                        strip_accents='unicode'
                    )),
                    ('clf', LogisticRegression(
                        C=1.0, 
                        max_iter=1000, 
                        class_weight='balanced'
                    ))
                ])

                pipeline.fit(X_train, y_train)

                # Evaluate
                y_pred = pipeline.predict(X_test)
                acc = accuracy_score(y_test, y_pred)
                report = classification_report(y_test, y_pred)

                # Save model
                joblib.dump(pipeline, MODEL_PATH)
                return pipeline, acc, report

            pipeline, acc, report = await asyncio.to_thread(_train_in_thread)
            
            self.model = pipeline
            self.is_trained = True

            return {
                'trained': True, 
                'samples': len(rows), 
                'accuracy': float(acc), 
                'report': report
            }

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {'trained': False, 'error': str(e)}

# Module-level singleton
classifier = SpamClassifier()
