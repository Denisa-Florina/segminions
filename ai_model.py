import numpy as np

class SegmentationModel:
    """
    Clasa responsabilă de inițializarea modelului și predicție.
    Pentru moment e un placeholder cu segmentare fake.
    """

    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.init_model()

    def init_model(self):
        """Inițializare model (fake)"""
        # TODO: Înlocuiește cu încărcarea modelului real
        
        print("Model placeholder inițializat")
        self.model_loaded = True

    def preprocess(self, image):
        """Preprocesare imagine înainte de predicție"""
        # TODO: Normalizare, resize, etc.

        img_min, img_max = np.min(image), np.max(image)
        return (image - img_min) / (img_max - img_min) if img_max - img_min != 0 else np.zeros_like(image)

    def predict(self, image):
        """
        Predicție pe imaginea normalizată
        Returnează: mask + metrics
        """
        # TODO: Înlocuiește cu predicția reală
        mask = self.segmentation(image)
        metrics = {
            'confidence': 0.87,
            'dice_score': 0.85,
            'iou_score': 0.78
        }
        return mask, metrics

    def segmentation(self, image):
        """Segmentare demo - cerc în centru"""
        mask = np.zeros_like(image)
        h, w = mask.shape
        rr, cc = np.ogrid[:h, :w]
        radius = min(h, w) // 100
        circle = (rr - h//2)**2 + (cc - w//2)**2 <= radius**2
        mask[circle] = 1
        return mask
