def build():
    from sklearn.linear_model import LogisticRegression

    return LogisticRegression(C=4.0, class_weight="balanced", max_iter=2000, random_state=42)
