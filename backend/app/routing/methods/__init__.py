"""Method selection lives here, not in UI branches or generator code.

To retain one method: set enabled_methods/default_method in config.yaml, then
optionally delete the unused module and weight file. Disabled methods are never loaded.
"""

from importlib import import_module

METHOD_LABELS = {"lr": "Logistic Regression (LR)", "svm": "Support Vector Machine (SVM)"}


def estimator(method: str):
    if method not in METHOD_LABELS:
        raise ValueError("unknown routing method")
    return import_module(f"app.routing.methods.{method}").build()
