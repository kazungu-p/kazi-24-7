import re

# Read the current template
with open('templates/index.html', 'r') as f:
    content = f.read()

# Find the jobs-grid section (from '<div class="jobs-grid">' to just before {% endblock %})
pattern = r'<div class="jobs-grid">[\s\S]*?(?=\s*{% endblock %})'
replacement = '''<div class="jobs-grid">
  {% if jobs %}
    {% for job in jobs %}
      <div class="job-card">
        <div class="job-card-body">
          <div class="job-header">
            <div style="flex: 1;">
              <h3 class="job-title">{{ job.title }}</h3>
              <div class="job-location">
                <i class="bi bi-geo-alt-fill"></i>
                {{ job.location }}
              </div>
            </div>
            <span class="status-badge status-{{ job.status }}">
              {{ job.status|capitalize }}
            </span>
          </div>

          {% set first_media = job.media|first %}
          {% if first_media %}
            <div class="media-preview">
              {% if current_user.is_authenticated %}
                {% if first_media.media_type == 'image' %}
                  <img src="{{ url_for('uploaded_file', filename=first_media.filename) }}"
                       alt="Job media for {{ job.title }}">
                {% elif first_media.media_type == 'video' %}
                  <video muted preload="metadata">
                    <source src="{{ url_for('uploaded_file', filename=first_media.filename) }}">
                    Your browser does not support the video tag.
                  </video>
                {% else %}
                  <div class="media-locked">
                    <a href="{{ url_for('uploaded_file', filename=first_media.filename) }}" target="_blank">
                      <i class="bi bi-file-earmark"></i>
                      View media
                    </a>
                  </div>
                {% endif %}
              {% else %}
                <div class="media-locked">
                  <a href="{{ url_for('login') }}">
                    <i class="bi bi-lock-fill"></i>
                    Login to view media
                  </a>
                </div>
              {% endif %}
            </div>
          {% endif %}

          <p class="job-description" id="desc-{{ job.id }}">{{ job.description }}</p>

          <div class="job-meta">
            <div class="poster-info">
              <div class="poster-name">
                Posted by <strong>{{ job.poster.username or job.poster.email }}</strong>
              </div>
              <div class="post-date">{{ job.created_at.strftime('%b %d, %Y at %H:%M') }}</div>
            </div>

            <div class="job-actions">
              {% if current_user.is_authenticated %}
                <form action="{{ url_for('apply_job', job_id=job.id) }}" method="post" style="margin: 0;">
                  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                  <button class="action-btn action-btn-apply" type="submit" title="Apply to this job">
                    <i class="bi bi-check-circle-fill"></i>
                    Apply
                  </button>
                </form>
              {% else %}
                <a class="action-btn action-btn-locked" href="{{ url_for('login') }}" title="Login to apply">
                  <i class="bi bi-lock-fill"></i>
                  Login
                </a>
              {% endif %}

              <a class="action-btn action-btn-details" href="{{ url_for('job_detail', job_id=job.id) }}" title="View details">
                <i class="bi bi-info-circle-fill"></i>
                Details
              </a>

              <button class="action-btn action-btn-icon copy-btn" 
                      data-copy-text="{{ url_for('job_detail', job_id=job.id, _external=true) }}" 
                      title="Copy job link">
                <i class="bi bi-link-45deg"></i>
              </button>
            </div>
          </div>
        </div>

        <div class="job-footer">
          <div class="job-id">#{{ job.id }}</div>
          <div class="footer-actions">
            <button class="copy-link copy-desc-btn" data-target="#desc-{{ job.id }}">
              <i class="bi bi-clipboard"></i> Copy description
            </button>
          </div>
        </div>
      </div>
    {% endfor %}
  {% else %}
    <div class="empty-state">
      <div class="empty-state-icon">
        <i class="bi bi-inbox"></i>
      </div>
      <h2 class="empty-state-title">No open jobs yet</h2>
      <p class="empty-state-text">Check back later or be the first to post an opportunity</p>
    </div>
  {% endif %}
</div>'''

# Replace the pattern
new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Also remove the debug CSS at the bottom if present
new_content = new_content.replace('''<style>
/* DEBUG: Force visibility */
.job-card {
    border: 5px solid red !important;
    background: yellow !important;
    display: block !important;
    opacity: 1 !important;
    visibility: visible !important;
    position: relative !important;
    z-index: 1000 !important;
}
.empty-state {
    border: 5px solid blue !important;
    background: cyan !important;
}
</style>''', '')

# Write back
with open('templates/index.html', 'w') as f:
    f.write(new_content)

print("Template fixed successfully!")
