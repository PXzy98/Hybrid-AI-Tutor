def build():
    from sklearn.svm import LinearSVC

    return LinearSVC(C=1.0, class_weight="balanced", random_state=42, max_iter=5000)
