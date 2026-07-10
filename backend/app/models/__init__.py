"""Import model modules that must be registered in shared SQLAlchemy metadata."""

# Clinical Context tables reference clinical_dictionary_concepts by foreign key.
# Import the dictionary models whenever app.models is loaded so SQLAlchemy can
# resolve those references during flushes and metadata sorting.
from app.models import clinical_dictionary as clinical_dictionary  # noqa: F401
