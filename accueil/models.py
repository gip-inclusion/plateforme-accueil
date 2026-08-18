from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


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
    content = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="textes personnalisés",
        help_text=(
            "Uniquement les textes qui remplacent ceux du code, au format JSON — "
            'par exemple {"note": "Mon texte"}. Vide : la section affiche les textes du code.'
        ),
    )

    class Meta:
        verbose_name = "section"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["page", "kind"], name="unique_kind_per_page"),
        ]

    def __str__(self):
        return f"{self.kind} ({self.position})"


@receiver(post_save, sender=Section)
@receiver(post_delete, sender=Section)
def _forget_cached_overrides(sender, **kwargs):
    """An edit shows up on the page at once, instead of waiting for the cache to
    lapse. Across several instances the TTL remains the upper bound: this only
    invalidates the cache of the process that saved."""
    from accueil.content import OVERRIDES_CACHE_KEY

    cache.delete(OVERRIDES_CACHE_KEY)
