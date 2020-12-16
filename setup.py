import setuptools

setuptools.setup(
    name="eol_progress_tab",
    version="0.0.1",
    author="matiassalinas",
    author_email="matsalinas@uchile.cl",
    description="Eol Student Progress Tab",
    long_description="Student progress tab with scaled grades",
    url="https://eol.uchile.cl",
    packages=setuptools.find_packages(),
    entry_points={
        "lms.djangoapp": [
            "eol_progress_tab = eol_progress_tab.apps:EolProgressTabConfig",
        ],
        "openedx.course_tab": [
            "eol_progress_tab = eol_progress_tab.plugins:EolProgressTab",
        ]
    },
)
