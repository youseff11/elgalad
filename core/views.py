import csv
import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .api_client import MAX_BATCH, PARAM_LIMITS, SummarizerClient, clean_params
from .file_extract import ExtractError, extract_text
from .forms import AIConfigForm, LoginForm, ProfileForm, RegisterForm, StyledPasswordChangeForm
from .i18n import SUPPORTED, translate
from .middleware import COOKIE_NAME
from .models import AIConfig, ApiCallLog, Summary

User = get_user_model()

MAX_INPUT_CHARS = 60_000


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def tr(request, key):
    return translate(key, getattr(request, "ui_lang", "ar"))


def word_count(text: str) -> int:
    return len((text or "").split())


def make_title(text: str, limit: int = 70) -> str:
    first = " ".join((text or "").split())
    return first if len(first) <= limit else first[:limit].rsplit(" ", 1)[0] + "…"


def api_error_message(request, result) -> str:
    if result.error == "connection":
        return tr(request, "err_connection")
    if result.error == "timeout":
        return tr(request, "err_timeout")
    if result.status == 400 and "empty" in (result.error or "").lower():
        return tr(request, "err_empty")
    return f"{tr(request, 'err_api')} — {result.error}"


def json_body(request) -> dict:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def safe_next(request, fallback="dashboard"):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return None


def summary_to_dict(request, s: Summary) -> dict:
    return {
        "id": s.pk,
        "title": s.title,
        "summary": s.summary,
        "language": s.language,
        "language_label": tr(request, f"lang_{s.language}"),
        "confidence": s.confidence,
        "input_words": s.input_words,
        "summary_words": s.summary_words,
        "compression": s.compression,
        "latency_ms": s.latency_ms,
        "token_stats": s.token_stats,
        "params": s.params,
        "cleaned_text": s.cleaned_text,
        "created_at": timezone.localtime(s.created_at).strftime("%Y-%m-%d %H:%M"),
        "url": f"/app/history/{s.pk}/",
    }


# ---------------------------------------------------------------------------
# public pages
# ---------------------------------------------------------------------------
def landing(request):
    return render(request, "public/landing.html", {
        "total_summaries": Summary.objects.count(),
        "total_users": User.objects.count(),
    })


def set_language(request, lang):
    target = safe_next(request) or request.META.get("HTTP_REFERER") or "/"
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = "/"
    resp = HttpResponseRedirect(target)
    if lang in SUPPORTED:
        resp.set_cookie(COOKIE_NAME, lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        if not request.POST.get("remember"):
            request.session.set_expiry(0)
        messages.success(request, tr(request, "msg_welcome_back"))
        return redirect(safe_next(request) or "dashboard")
    return render(request, "auth/login.html", {"form": form, "next": request.GET.get("next", "")})


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # The very first account on a fresh install becomes the site administrator.
        if not User.objects.filter(is_superuser=True).exclude(pk=user.pk).exists():
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])
        login(request, user)
        messages.success(request, tr(request, "msg_account_created"))
        return redirect("dashboard")
    return render(request, "auth/register.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("landing")


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------
def _scope_queryset(request):
    scope = request.GET.get("scope", "me")
    if request.user.is_staff and scope == "all":
        return Summary.objects.all(), ApiCallLog.objects.all(), "all"
    return (
        Summary.objects.filter(user=request.user),
        ApiCallLog.objects.filter(user=request.user),
        "me",
    )


@login_required
def dashboard(request):
    qs, logs, scope = _scope_queryset(request)
    now = timezone.now()
    today = timezone.localdate()

    agg = qs.aggregate(
        total=Count("id"),
        words_in=Sum("input_words"),
        words_out=Sum("summary_words"),
        avg_latency=Avg("latency_ms", filter=Q(kind=Summary.KIND_SINGLE)),
    )
    total = agg["total"] or 0
    words_in = agg["words_in"] or 0
    words_out = agg["words_out"] or 0
    compression = max(0.0, round((1 - words_out / words_in) * 100, 1)) if words_in else 0
    avg_latency_s = round((agg["avg_latency"] or 0) / 1000, 2)

    this_week = qs.filter(created_at__gte=now - timedelta(days=7)).count()
    prev_week = qs.filter(created_at__gte=now - timedelta(days=14), created_at__lt=now - timedelta(days=7)).count()
    week_delta = None
    if prev_week:
        week_delta = round((this_week - prev_week) / prev_week * 100)

    # --- activity: last 14 days
    start = today - timedelta(days=13)
    daily = {
        row["d"]: row["c"]
        for row in qs.filter(created_at__date__gte=start)
        .annotate(d=TruncDate("created_at"))
        .order_by()
        .values("d")
        .annotate(c=Count("id"))
    }
    activity = []
    for i in range(14):
        d = start + timedelta(days=i)
        activity.append({"date": d.strftime("%m-%d"), "count": daily.get(d, 0)})

    # --- language distribution + compression per language
    lang_rows = qs.order_by().values("language").annotate(
        c=Count("id"), wi=Sum("input_words"), wo=Sum("summary_words")
    )
    languages, compression_by_lang = [], []
    order = {"ar": 0, "en": 1, "mixed": 2, "unknown": 3}
    for row in sorted(lang_rows, key=lambda r: order.get(r["language"], 9)):
        label = tr(request, f"lang_{row['language']}")
        languages.append({"code": row["language"], "label": label, "count": row["c"]})
        if row["wi"]:
            compression_by_lang.append({
                "code": row["language"], "label": label,
                "value": max(0.0, round((1 - (row["wo"] or 0) / row["wi"]) * 100, 1)),
            })

    # --- latency trend: last 20 single summaries
    latency = [
        {"label": timezone.localtime(s.created_at).strftime("%m-%d %H:%M"), "value": round(s.latency_ms / 1000, 2)}
        for s in reversed(list(qs.filter(kind=Summary.KIND_SINGLE, latency_ms__isnull=False)[:20]))
    ]

    # --- API health (7 days)
    week_logs = logs.filter(created_at__gte=now - timedelta(days=7))
    log_agg = week_logs.aggregate(total=Count("id"), ok=Count("id", filter=Q(ok=True)))
    success_rate = round(log_agg["ok"] / log_agg["total"] * 100, 1) if log_agg["total"] else None

    chart_data = {
        "activity": activity,
        "languages": languages,
        "compression": compression_by_lang,
        "latency": latency,
    }

    return render(request, "app/dashboard.html", {
        "page": "dashboard",
        "scope": scope,
        "kpi": {
            "total": total,
            "words_in": words_in,
            "compression": compression,
            "avg_latency_s": avg_latency_s,
            "this_week": this_week,
            "week_delta": week_delta,
            "success_rate": success_rate,
            "api_calls": log_agg["total"],
            "favorites": qs.filter(is_favorite=True).count(),
        },
        "chart_data": chart_data,
        "recent": qs.select_related("user")[:6],
        "api_url": AIConfig.get().effective_url,
    })


# ---------------------------------------------------------------------------
# summarize (single)
# ---------------------------------------------------------------------------
@login_required
def summarize_page(request):
    cfg = AIConfig.get()
    return render(request, "app/summarize.html", {
        "page": "summarize",
        "defaults": cfg.default_params(),
        "limits": {k: [v[0], v[1]] for k, v in PARAM_LIMITS.items()},
        "max_chars": MAX_INPUT_CHARS,
    })


def _validate_text(request, text):
    if not text:
        return JsonResponse({"ok": False, "error": tr(request, "err_empty")}, status=400)
    if len(text) > MAX_INPUT_CHARS:
        return JsonResponse({"ok": False, "error": tr(request, "err_too_long")}, status=400)
    return None


def _fallback_response(request, result):
    """Server could not reach the model (e.g. PythonAnywhere free-plan whitelist).
    Tell the browser to call the model directly and send the result back to be saved."""
    return JsonResponse({
        "ok": False,
        "fallback": True,
        "base_url": AIConfig.get().effective_url,
        "error": api_error_message(request, result),
    }, status=502)


def _save_single(request, text, params, file_name, d, latency_ms):
    summary_text = (d.get("summary") or "").strip()
    return Summary.objects.create(
        user=request.user,
        kind=Summary.KIND_SINGLE,
        source_type=Summary.SOURCE_FILE if file_name else Summary.SOURCE_TEXT,
        file_name=(file_name or "")[:255],
        title=make_title(file_name or text),
        input_text=text,
        cleaned_text=str(d.get("cleaned_text") or "")[:MAX_INPUT_CHARS],
        summary=summary_text[:MAX_INPUT_CHARS],
        language=d.get("language") if d.get("language") in ("ar", "en", "mixed") else "unknown",
        confidence=d.get("confidence") if isinstance(d.get("confidence"), (int, float)) else None,
        input_words=word_count(text),
        summary_words=word_count(summary_text),
        latency_ms=d.get("latency_ms") if isinstance(d.get("latency_ms"), (int, float)) else latency_ms,
        params=d.get("generation_config") if isinstance(d.get("generation_config"), dict) else params,
        token_stats=d.get("token_stats") if isinstance(d.get("token_stats"), dict) else {},
    )


def _log_browser_call(request, endpoint, ok, latency_ms, status_code=None, error=""):
    try:
        latency_ms = float(latency_ms) if latency_ms is not None else None
    except (TypeError, ValueError):
        latency_ms = None
    ApiCallLog.objects.create(
        user=request.user, endpoint=str(endpoint)[:100], method="BROWSER",
        status_code=status_code if isinstance(status_code, int) else None,
        ok=bool(ok), latency_ms=latency_ms, error=str(error or "")[:1000],
    )


@login_required
@require_POST
def api_summarize(request):
    body = json_body(request)
    text = (body.get("text") or "").strip()
    bad = _validate_text(request, text)
    if bad:
        return bad

    client = SummarizerClient(user=request.user)
    params = clean_params(body.get("params"), defaults=client.config.default_params())
    result = client.summarize(text, params)
    if result.error == "connection":
        return _fallback_response(request, result)
    if not result.ok or not result.data.get("success", True):
        return JsonResponse({"ok": False, "error": api_error_message(request, result)}, status=502)

    s = _save_single(request, text, params, body.get("file_name"), result.data, result.latency_ms)
    return JsonResponse({"ok": True, "result": summary_to_dict(request, s)})


@login_required
@require_POST
def api_summarize_save(request):
    """Browser-mode: the page called the model itself and sends the response here to be stored."""
    body = json_body(request)
    text = (body.get("text") or "").strip()
    bad = _validate_text(request, text)
    if bad:
        return bad
    d = body.get("data") if isinstance(body.get("data"), dict) else {}
    latency = body.get("latency_ms")
    _log_browser_call(request, "/api/v1/summarize", bool(d.get("summary")), latency)
    if not d.get("summary"):
        return JsonResponse({"ok": False, "error": tr(request, "err_api")}, status=400)
    params = clean_params(body.get("params"), defaults=AIConfig.get().default_params())
    s = _save_single(request, text, params, body.get("file_name"), d,
                     latency if isinstance(latency, (int, float)) else None)
    return JsonResponse({"ok": True, "result": summary_to_dict(request, s)})


@login_required
@require_POST
def api_log_call(request):
    """Browser-mode: record a direct call (tools / failures) in the monitoring log."""
    body = json_body(request)
    _log_browser_call(request, body.get("endpoint") or "?", body.get("ok"), body.get("latency_ms"),
                      body.get("status"), body.get("error"))
    return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# batch
# ---------------------------------------------------------------------------
@login_required
def batch_page(request):
    cfg = AIConfig.get()
    return render(request, "app/batch.html", {
        "page": "batch",
        "defaults": cfg.default_params(),
        "max_batch": MAX_BATCH,
    })


def _batch_texts(request, body):
    texts = [str(t).strip() for t in (body.get("texts") or []) if str(t).strip()]
    if not texts:
        return None, JsonResponse({"ok": False, "error": tr(request, "err_empty")}, status=400)
    if len(texts) > MAX_BATCH:
        return None, JsonResponse({"ok": False, "error": tr(request, "err_batch_limit")}, status=400)
    if any(len(t) > MAX_INPUT_CHARS for t in texts):
        return None, JsonResponse({"ok": False, "error": tr(request, "err_too_long")}, status=400)
    return texts, None


def _save_batch(request, texts, params, data, latency_ms):
    batch_id = uuid.uuid4()
    rows = [r for r in (data.get("results") or []) if isinstance(r, dict)]
    total_latency = data.get("total_latency_ms")
    if not isinstance(total_latency, (int, float)):
        total_latency = latency_ms or 0
    per_item_latency = round(total_latency / max(len(rows), 1), 2)
    saved = []
    for row in rows:
        idx = row.get("index", len(saved))
        if not isinstance(idx, int) or idx >= len(texts) or idx < 0:
            idx = min(len(saved), len(texts) - 1)
        src = texts[idx]
        summary_text = str(row.get("summary") or "").strip()
        s = Summary.objects.create(
            user=request.user,
            kind=Summary.KIND_BATCH,
            batch_id=batch_id,
            title=make_title(src),
            input_text=src,
            summary=summary_text[:MAX_INPUT_CHARS],
            language=row.get("language") if row.get("language") in ("ar", "en", "mixed") else "unknown",
            confidence=row.get("confidence") if isinstance(row.get("confidence"), (int, float)) else None,
            input_words=word_count(src),
            summary_words=word_count(summary_text),
            latency_ms=per_item_latency,
            params=params,
            token_stats=row.get("token_stats") if isinstance(row.get("token_stats"), dict) else {},
        )
        item = summary_to_dict(request, s)
        item["index"] = idx
        saved.append(item)
    return {
        "ok": True,
        "batch_id": str(batch_id),
        "count": len(saved),
        "total_latency_ms": total_latency,
        "results": saved,
    }


@login_required
@require_POST
def api_batch(request):
    body = json_body(request)
    texts, bad = _batch_texts(request, body)
    if bad:
        return bad

    client = SummarizerClient(user=request.user)
    result = client.summarize_batch(texts, body.get("params"))
    if result.error == "connection":
        return _fallback_response(request, result)
    if not result.ok or not result.data.get("success", True):
        return JsonResponse({"ok": False, "error": api_error_message(request, result)}, status=502)

    params = clean_params(body.get("params"), allowed=("max_length", "min_length", "num_beams"),
                          defaults=client.config.default_params())
    return JsonResponse(_save_batch(request, texts, params, result.data, result.latency_ms))


@login_required
@require_POST
def api_batch_save(request):
    """Browser-mode counterpart of api_batch."""
    body = json_body(request)
    texts, bad = _batch_texts(request, body)
    if bad:
        return bad
    d = body.get("data") if isinstance(body.get("data"), dict) else {}
    latency = body.get("latency_ms")
    _log_browser_call(request, "/api/v1/summarize/batch", bool(d.get("results")), latency)
    if not d.get("results"):
        return JsonResponse({"ok": False, "error": tr(request, "err_api")}, status=400)
    params = clean_params(body.get("params"), allowed=("max_length", "min_length", "num_beams"),
                          defaults=AIConfig.get().default_params())
    return JsonResponse(_save_batch(request, texts, params, d,
                                    latency if isinstance(latency, (int, float)) else None))


# ---------------------------------------------------------------------------
# NLP tools
# ---------------------------------------------------------------------------
@login_required
def tools_page(request):
    return render(request, "app/tools.html", {"page": "tools"})


@login_required
@require_POST
def api_tool(request, tool):
    body = json_body(request)
    text = (body.get("text") or "").strip()
    if not text:
        return JsonResponse({"ok": False, "error": tr(request, "err_empty")}, status=400)
    if len(text) > MAX_INPUT_CHARS:
        return JsonResponse({"ok": False, "error": tr(request, "err_too_long")}, status=400)
    language = body.get("language") or None

    client = SummarizerClient(user=request.user)
    if tool == "detect":
        result = client.detect_language(text)
    elif tool == "clean":
        result = client.clean_text(text, language)
    elif tool == "tokenize":
        result = client.tokenize(text, language)
    else:
        return JsonResponse({"ok": False, "error": "unknown tool"}, status=404)

    if result.error == "connection":
        return _fallback_response(request, result)
    if not result.ok:
        return JsonResponse({"ok": False, "error": api_error_message(request, result)}, status=502)
    data = dict(result.data)
    lang = data.get("language") or data.get("language_applied")
    if lang:
        data["language_label"] = tr(request, f"lang_{lang}")
    return JsonResponse({"ok": True, "result": data, "latency_ms": result.latency_ms})


@login_required
@require_POST
def api_extract(request):
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"ok": False, "error": tr(request, "err_no_file")}, status=400)
    try:
        text = extract_text(f)
    except ExtractError as exc:
        return JsonResponse({"ok": False, "error": tr(request, f"err_file_{exc}")}, status=400)
    except Exception:
        return JsonResponse({"ok": False, "error": tr(request, "err_file_read")}, status=400)
    return JsonResponse({"ok": True, "text": text[:MAX_INPUT_CHARS], "file_name": f.name,
                         "words": word_count(text), "truncated": len(text) > MAX_INPUT_CHARS})


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------
def _history_queryset(request):
    if request.user.is_staff and request.GET.get("scope") == "all":
        qs = Summary.objects.select_related("user")
    else:
        qs = Summary.objects.filter(user=request.user)
    q = request.GET.get("q", "").strip()
    lang = request.GET.get("lang", "")
    kind = request.GET.get("kind", "")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(input_text__icontains=q) | Q(summary__icontains=q))
    if lang in ("ar", "en", "mixed"):
        qs = qs.filter(language=lang)
    if kind in (Summary.KIND_SINGLE, Summary.KIND_BATCH):
        qs = qs.filter(kind=kind)
    if request.GET.get("fav") == "1":
        qs = qs.filter(is_favorite=True)
    return qs


def _get_summary_for(request, pk):
    if request.user.is_staff:
        return get_object_or_404(Summary, pk=pk)
    return get_object_or_404(Summary, pk=pk, user=request.user)


@login_required
def history(request):
    qs = _history_queryset(request)
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "app/history.html", {
        "page": "history",
        "page_obj": page_obj,
        "total": paginator.count,
        "filters": {
            "q": request.GET.get("q", ""),
            "lang": request.GET.get("lang", ""),
            "kind": request.GET.get("kind", ""),
            "fav": request.GET.get("fav", ""),
            "scope": request.GET.get("scope", ""),
        },
        "querystring": params.urlencode(),
    })


@login_required
def history_detail(request, pk):
    s = _get_summary_for(request, pk)
    batch_items = []
    if s.batch_id:
        batch_items = Summary.objects.filter(batch_id=s.batch_id).exclude(pk=s.pk).order_by("pk")
    return render(request, "app/history_detail.html", {
        "page": "history",
        "s": s,
        "batch_items": batch_items,
        "params_json": s.params,
    })


@login_required
@require_POST
def history_delete(request, pk):
    s = _get_summary_for(request, pk)
    s.delete()
    messages.success(request, tr(request, "msg_deleted"))
    return redirect(safe_next(request) or "history")


@login_required
@require_POST
def history_favorite(request, pk):
    s = _get_summary_for(request, pk)
    s.is_favorite = not s.is_favorite
    s.save(update_fields=["is_favorite"])
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"ok": True, "favorite": s.is_favorite})
    return redirect(safe_next(request) or "history")


@login_required
def history_export(request):
    qs = _history_queryset(request)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    resp["Content-Disposition"] = f'attachment; filename="summaries-{stamp}.csv"'
    resp.write("﻿")  # BOM so Excel opens Arabic correctly
    w = csv.writer(resp)
    w.writerow(["id", "created_at", "user", "kind", "language", "confidence", "input_words",
                "summary_words", "compression_%", "latency_ms", "title", "summary", "input_text"])
    for s in qs.select_related("user").iterator():
        w.writerow([s.pk, timezone.localtime(s.created_at).strftime("%Y-%m-%d %H:%M"), s.user.username,
                    s.kind, s.language, s.confidence, s.input_words, s.summary_words, s.compression,
                    s.latency_ms, s.title, s.summary, s.input_text])
    return resp


@login_required
def history_download(request, pk):
    s = _get_summary_for(request, pk)
    body = (
        f"{s.title}\n{'=' * 40}\n\n"
        f"[{translate('summary', request.ui_lang)}]\n{s.summary}\n\n"
        f"[{translate('original_text', request.ui_lang)}]\n{s.input_text}\n"
    )
    resp = HttpResponse(body, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="summary-{s.pk}.txt"'
    return resp


# ---------------------------------------------------------------------------
# API monitoring
# ---------------------------------------------------------------------------
@login_required
def api_status_page(request):
    now = timezone.now()
    logs = ApiCallLog.objects.all() if request.user.is_staff else ApiCallLog.objects.filter(user=request.user)
    week = logs.filter(created_at__gte=now - timedelta(days=7))
    by_endpoint = list(
        week.order_by().values("endpoint")
        .annotate(total=Count("id"), ok=Count("id", filter=Q(ok=True)), avg=Avg("latency_ms"), mx=Max("latency_ms"))
        .order_by("-total")
    )
    for row in by_endpoint:
        row["avg_s"] = round((row["avg"] or 0) / 1000, 2)
        row["max_s"] = round((row["mx"] or 0) / 1000, 2)
        row["rate"] = round(row["ok"] / row["total"] * 100, 1) if row["total"] else 0
    agg = week.aggregate(total=Count("id"), ok=Count("id", filter=Q(ok=True)), avg=Avg("latency_ms"))
    return render(request, "app/api_status.html", {
        "page": "api",
        "api_url": AIConfig.get().effective_url,
        "by_endpoint": by_endpoint,
        "chart_endpoints": [{"label": r["endpoint"], "value": r["avg_s"]} for r in by_endpoint],
        "agg": {
            "total": agg["total"] or 0,
            "ok": agg["ok"] or 0,
            "errors": (agg["total"] or 0) - (agg["ok"] or 0),
            "rate": round(agg["ok"] / agg["total"] * 100, 1) if agg["total"] else None,
            "avg_s": round((agg["avg"] or 0) / 1000, 2),
        },
        "recent_logs": logs.select_related("user")[:25],
    })


@login_required
@require_GET
def api_health_json(request):
    client = SummarizerClient(user=request.user)
    cache_key = f"ai-health:{client.base_url}:{request.ui_lang}"
    force = request.GET.get("force") == "1"
    payload = None if force else cache.get(cache_key)
    if payload is None:
        health = client.health()
        info = client.info() if health.ok else None
        payload = {
            "ok": health.ok and bool(health.data.get("model_loaded", True)),
            "reachable": health.ok,
            "latency_ms": health.latency_ms,
            "health": health.data,
            "info": info.data if info and info.ok else {},
            "error": "" if health.ok else api_error_message(request, health),
            "base_url": client.base_url,
        }
        cache.set(cache_key, payload, 20)
    return JsonResponse(payload)


# ---------------------------------------------------------------------------
# settings + users
# ---------------------------------------------------------------------------
@login_required
def settings_page(request):
    profile_form = ProfileForm(instance=request.user)
    password_form = StyledPasswordChangeForm(request.user)
    cfg = AIConfig.get()
    ai_form = AIConfigForm(instance=cfg) if request.user.is_staff else None
    active = request.GET.get("tab", "profile")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "profile":
            active = "profile"
            profile_form = ProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, tr(request, "msg_saved"))
                return redirect(f"{request.path}?tab=profile")
        elif action == "password":
            active = "password"
            password_form = StyledPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, tr(request, "msg_password_changed"))
                return redirect(f"{request.path}?tab=password")
        elif action == "ai" and request.user.is_staff:
            active = "ai"
            ai_form = AIConfigForm(request.POST, instance=cfg)
            if ai_form.is_valid():
                ai_form.save()
                messages.success(request, tr(request, "msg_saved"))
                return redirect(f"{request.path}?tab=ai")
        messages.error(request, tr(request, "msg_fix_errors"))

    return render(request, "app/settings.html", {
        "page": "settings",
        "tab": active,
        "profile_form": profile_form,
        "password_form": password_form,
        "ai_form": ai_form,
        "env_url": settings.AI_API_BASE_URL,
        "effective_url": cfg.effective_url,
    })


@staff_member_required
def users_page(request):
    users = (
        User.objects.annotate(
            n=Count("summaries", distinct=True),
            words=Sum("summaries__input_words"),
            last=Max("summaries__created_at"),
        ).order_by("-n", "-date_joined")
    )
    return render(request, "app/users.html", {"page": "users", "users": users})


@staff_member_required
@require_POST
def user_toggle_staff(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u != request.user:
        u.is_staff = not u.is_staff
        u.save(update_fields=["is_staff"])
        messages.success(request, tr(request, "msg_saved"))
    return redirect("users")
