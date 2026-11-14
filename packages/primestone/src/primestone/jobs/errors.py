class PermanentError(Exception):
    """Erreur non réessayable (entrée invalide, gestionnaire inconnu…) : étape marquée DEAD."""
