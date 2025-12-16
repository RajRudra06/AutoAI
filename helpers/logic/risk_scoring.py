import numpy as np

def transform_scores_to_risk(scores, scale=5.0):
  
    scores = np.asarray(scores)
    return 1 / (1 + np.exp(scores * scale))
