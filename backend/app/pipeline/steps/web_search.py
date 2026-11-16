from time import perf_counter

from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep
from app.pipeline.steps.generate import llm_flags_health
from app.privacy.profiles import search_query
from app.websearch import allowlist_for, engines_for, web_search


@steps.register("web_search")
class WebSearchStep(BaseStep):
    """Adds web passages from allowed sites to a cloud answer that needs recent information (task T13; guide
    4.5 step 6a). Runs only when search is configured, the question goes to the cloud model and the semantic
    router found that it needs recent information. The query is `search_query()` (rule 5): built from the
    sanitized question only, and None (no search) when nothing general and safe is left."""

    name = "web_search"
    on_error = "skip"  # a failed search leaves the course passages only

    async def run(self, ctx: RequestContext) -> RequestContext:
        settings = self.services.settings
        if settings.websearch.provider == "off":
            return ctx
        analysis = ctx.semantic_analysis
        if ctx.target != "cloud" or analysis is None or not analysis.requires_fresh_evidence:
            return ctx
        # the local model's health check runs before anything leaves (it would otherwise only run when the
        # generate step builds the cloud request): a flagged question is not cloud-safe, so no query below
        if ctx.pii is not None and ctx.pii.cloud_safe and await llm_flags_health(ctx, self.services):
            ctx.pii = ctx.pii.model_copy(update={"cloud_safe": False})
        query = search_query(ctx)
        if query is None:
            await ctx.report("web_search", "skipped",
                             "No general query could be made without personal details.")
            return ctx
        course_type = ctx.settings.course_type if ctx.settings else None
        t0 = perf_counter()
        await ctx.report("web_search", "running", "Searching allowed sites for recent information.")
        try:
            found = await web_search(query, allowlist_for(course_type, settings),
                                     engines=engines_for(course_type, settings), settings=settings)
        except Exception:
            await ctx.report("web_search", "failed", "Web search failed; course material only.",
                             (perf_counter() - t0) * 1000)
            return ctx
        ctx.passages = [*ctx.passages, *found]
        await ctx.report("web_search", "completed", f"Added {len(found)} web passages.",
                         (perf_counter() - t0) * 1000)
        return ctx
