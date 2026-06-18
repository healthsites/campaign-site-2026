#!/bin/bash

# Backup templates
cp theme/templates/region.html theme/templates/region.html.bak
cp theme/templates/country.html theme/templates/country.html.bak

echo "✓ Backups created"

# Update region.html - Add map container and Leaflet JS
cat > theme/templates/region.html << 'REGION'
{% extends "base.html" %}

{% block extra_head %}
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
{% endblock %}

{% block content %}
{% set is_fr = (page and page.lang == 'fr') or DEFAULT_LANG == 'fr' %}
{% set is_pt = (page and page.lang == 'pt') or DEFAULT_LANG == 'pt' %}
{% set is_ar = (page and page.lang == 'ar') or DEFAULT_LANG == 'ar' %}
{% set lang_prefix = '/fr' if is_fr else '/pt' if is_pt else '/ar' if is_ar else '' %}

<section class="region-header">
    <div class="container">
        <nav class="breadcrumb">
            <a href="{{ lang_prefix }}/campaigns/">
                {% if is_fr %}Campagnes{% elif is_pt %}Campanhas{% elif is_ar %}الحملات{% else %}Campaigns{% endif %}
            </a>
            →
            <a href="{{ lang_prefix }}/campaigns/{{ page.country_slug|default(page.country|lower) }}/">
                {{ page.country }}
            </a>
            →
            <span>{{ page.region }}</span>
        </nav>

        <h1>{{ page.title }}</h1>

        {% if page.campaign_status %}
        <p class="campaign-status status-{{ page.campaign_status|lower|replace(' ', '-') }}">
            {{ page.campaign_status }}
        </p>
        {% endif %}
    </div>
</section>

{# ── LEAFLET MAP OR STATIC IMAGE ─────────────────────────────────────── #}
{% if page.geojson_file %}
<section class="page-map">
    <div class="container">
        <div id="map" class="campaign-map" role="img" aria-label="Map of {{ page.region }}"></div>
    </div>
</section>
{% elif page.map_image %}
<section class="page-map">
    <div class="container">
        <figure>
            <img src="{{ page.map_image }}"
                 alt="{{ page.map_alt if page.map_alt else 'Map of ' ~ page.country }}">
            {% if page.map_caption %}
            <figcaption>{{ page.map_caption }}</figcaption>
            {% endif %}
        </figure>
    </div>
</section>
{% endif %}

<section class="region-content">
    <div class="container">
        <div class="region-layout">
            <article class="content">
                {{ page.content }}
            </article>

            <aside class="region-sidebar">

                {# ── PHASE 1 STATS ─────────────────────────────────────────── #}
                <div class="campaign-stats">
                    <h3>
                        {% if page.phase2_status %}
                            {% if is_fr %}Phase 1 — Résultats{% elif is_pt %}Fase 1 — Resultados{% else %}Phase 1 — Results{% endif %}
                        {% else %}
                            {% if is_fr %}Statistiques{% elif is_pt %}Estatísticas{% elif is_ar %}إحصائيات{% else %}Campaign Stats{% endif %}
                        {% endif %}
                    </h3>

                    {% if page.budget_needed %}
                    <div class="stat">
                        <strong>{% if is_fr %}Budget Nécessaire{% elif is_pt %}Orçamento Necessário{% elif is_ar %}الميزانية المطلوبة{% else %}Budget Needed{% endif %}</strong>
                        <span>{{ page.budget_needed }}</span>
                    </div>
                    {% endif %}

                    {% if page.facilities_target %}
                    <div class="stat">
                        <strong>{% if is_fr %}Établissements Cibles{% elif is_pt %}Estabelecimentos Alvo{% elif is_ar %}المرافق المستهدفة{% else %}Target Facilities{% endif %}</strong>
                        <span>{{ page.facilities_target }}+</span>
                    </div>
                    {% endif %}

                    {% if page.facilities_validated %}
                    <div class="stat">
                        <strong>{% if is_fr %}Établissements Validés{% elif is_pt %}Estabelecimentos Validados{% elif is_ar %}المرافق المُتحقق منها{% else %}Facilities Validated{% endif %}</strong>
                        <span>{{ page.facilities_validated }}</span>
                    </div>
                    {% endif %}

                    {% if page.emergency_facilities %}
                    <div class="stat">
                        <strong>{% if is_fr %}Services d'Urgence Identifiés{% elif is_pt %}Serviços de Emergência Identificados{% else %}Emergency Facilities Identified{% endif %}</strong>
                        <span>{{ page.emergency_facilities }}</span>
                    </div>
                    {% endif %}

                    {% if page.start_date %}
                    <div class="stat">
                        <strong>{% if is_fr %}Date de Début{% elif is_pt %}Data de Início{% elif is_ar %}تاريخ البدء{% else %}Start Date{% endif %}</strong>
                        <span>{{ page.start_date }}</span>
                    </div>
                    {% endif %}
                </div>

                {# Phase 1 CTAs #}
                <div class="campaign-actions">
                    <a href="{{ page.cta_primary_url if page.cta_primary_url else 'https://healthsites.io/contact' }}"
                       class="btn btn-primary"
                       {% if page.cta_primary_url and page.cta_primary_url.startswith('http') %}target="_blank" rel="noopener"{% endif %}>
                        {{ page.cta_primary_label if page.cta_primary_label else 'Support' }}
                    </a>

                    <a href="{{ page.cta_secondary_url if page.cta_secondary_url else 'https://healthsites.io/map' }}"
                       class="btn btn-secondary"
                       {% if page.cta_secondary_url and page.cta_secondary_url.startswith('http') %}target="_blank" rel="noopener"{% endif %}>
                        {{ page.cta_secondary_label if page.cta_secondary_label else 'Map' }}
                    </a>
                </div>

                {# ── PHASE 2 BLOCK ─── #}
                {% if page.phase2_status %}
                <div class="campaign-stats phase2-block">
                    <h3>{% if is_fr %}Phase 2 — Prochaine Étape{% elif is_pt %}Fase 2 — Próxima Etapa{% else %}Phase 2 — Next Step{% endif %}</h3>

                    <div class="stat">
                        <strong>{% if is_fr %}Statut{% elif is_pt %}Estado{% else %}Status{% endif %}</strong>
                        <span>{{ page.phase2_status }}</span>
                    </div>

                    {% if page.phase2_target %}
                    <div class="stat">
                        <strong>{% if is_fr %}Établissements à Confirmer{% elif is_pt %}Estabelecimentos a Confirmar{% else %}Facilities to Confirm{% endif %}</strong>
                        <span>{{ page.phase2_target }}</span>
                    </div>
                    {% endif %}

                    {% if page.phase2_budget %}
                    <div class="stat">
                        <strong>{% if is_fr %}Budget Estimé{% elif is_pt %}Orçamento Estimado{% else %}Estimated Budget{% endif %}</strong>
                        <span>{{ page.phase2_budget }}</span>
                    </div>
                    {% endif %}
                </div>

                <div class="campaign-actions">
                    <a href="{{ page.phase2_cta_url if page.phase2_cta_url else 'https://healthsites.io/contact' }}"
                       class="btn btn-primary"
                       target="_blank" rel="noopener">
                        {{ page.phase2_cta_label if page.phase2_cta_label else 'Support Phase 2' }}
                    </a>
                </div>
                {% endif %}

            </aside>
        </div>
    </div>
</section>
{% endblock %}

{% block extra_js %}
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>

<script>
(function () {
    var mapEl = document.getElementById('map');
    if (!mapEl || typeof L === 'undefined') return;

    var center = [14.5, -14.5];
    var map = L.map('map').setView(center, 6);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    {% if page.geojson_file %}
    var geoJsonUrl = '{{ SITEURL }}/theme/geojson/{{ page.geojson_file }}';
    
    fetch(geoJsonUrl)
        .then(response => response.json())
        .then(geojson => {
            L.geoJSON(geojson, {
                style: {
                    color: '#000000',
                    weight: 1,
                    opacity: 0.8,
                    fillColor: '#ffffff',
                    fillOpacity: 0
                }
            }).addTo(map);
        })
        .catch(error => console.error('Error loading GeoJSON:', error));
    {% endif %}
})();
</script>
{% endblock %}
REGION

echo "✅ region.html updated"
