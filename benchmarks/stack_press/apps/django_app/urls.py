from __future__ import annotations

import contextlib
import json

from benchmarks.stack_press.apps.django_app.models import Item
from django.db.models import Max
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok", "stack": "django"})


def stats(_request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "count": Item.objects.count(),
            "max_id": Item.objects.aggregate(m=Max("id"))["m"] or 0,
        }
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def items_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        try:
            limit = int(request.GET.get("limit", "50"))
        except ValueError:
            limit = 50
        try:
            offset = int(request.GET.get("offset", "0"))
        except ValueError:
            offset = 0
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        qs = Item.objects.all()
        cat = request.GET.get("category")
        if cat:
            qs = qs.filter(category=cat)
        min_score = request.GET.get("min_score")
        if min_score is not None and min_score != "":
            with contextlib.suppress(ValueError):
                qs = qs.filter(score__gte=int(min_score))
        q = request.GET.get("q")
        if q:
            qs = qs.filter(name__startswith=q)
        rows = list(qs[offset : offset + limit].values("id", "name", "notes", "category", "score"))
        return JsonResponse(rows, safe=False)

    try:
        body = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "invalid json"}, status=400)
    name = body.get("name")
    if not name or not isinstance(name, str):
        return JsonResponse({"detail": "name required"}, status=422)
    item = Item.objects.create(
        name=name,
        notes=body.get("notes"),
        category=body.get("category") or "general",
        score=int(body.get("score") or 0),
    )
    return JsonResponse(
        {
            "id": item.id,
            "name": item.name,
            "notes": item.notes,
            "category": item.category,
            "score": item.score,
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def items_detail(request: HttpRequest, item_id: int) -> HttpResponse:
    try:
        item = Item.objects.get(pk=item_id)
    except Item.DoesNotExist:
        return JsonResponse({"detail": "not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(
            {
                "id": item.id,
                "name": item.name,
                "notes": item.notes,
                "category": item.category,
                "score": item.score,
            }
        )

    if request.method == "DELETE":
        item.delete()
        return HttpResponse(status=204)

    try:
        body = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "invalid json"}, status=400)
    if "name" in body and body["name"] is not None:
        item.name = body["name"]
    if "notes" in body:
        item.notes = body["notes"]
    if "category" in body and body["category"] is not None:
        item.category = body["category"]
    if "score" in body and body["score"] is not None:
        item.score = int(body["score"])
    item.save()
    return JsonResponse(
        {
            "id": item.id,
            "name": item.name,
            "notes": item.notes,
            "category": item.category,
            "score": item.score,
        }
    )


urlpatterns = [
    path("health", health),
    path("stats", stats),
    path("items", items_collection),
    path("items/<int:item_id>", items_detail),
]
