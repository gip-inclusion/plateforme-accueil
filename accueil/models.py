from django.db import models


class Page(models.Model):
    """A page of the showcase. There is only one for now; it exists so that
    page-level settings and publications have somewhere to live."""

    slug = models.SlugField(unique=True, default="accueil", verbose_name="identifiant")
    label = models.CharField(max_length=120, default="Accueil", verbose_name="nom")

    class Meta:
        verbose_name = "page"

    def __str__(self):
        return self.label


class Section(models.Model):
    """Editor overrides for one section of a page.

    A section's content, order and template all have defaults declared in
    `accueil/sections/`; this table only records what an editor changed. A row
    whose `content` is empty renders exactly like the code.
    """

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="sections")
    kind = models.CharField(max_length=40, verbose_name="type de section")
    position = models.PositiveIntegerField(verbose_name="ordre")
    active = models.BooleanField(default=True, verbose_name="affichée")
    content = models.JSONField(default=dict, blank=True, verbose_name="écarts au texte du code")

    class Meta:
        verbose_name = "section"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["page", "kind"], name="unique_kind_per_page"),
        ]

    def __str__(self):
        return f"{self.kind} ({self.position})"
