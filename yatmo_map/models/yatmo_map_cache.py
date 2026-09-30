# Key/value store with an expiry, the Odoo counterpart of the WordPress transients: neighbourhood
# texts (30 days) and geocoding results (90 days) are looked up once, not on every page view.
import json
from datetime import timedelta

from odoo import api, fields, models


class YatmoMapCache(models.Model):
    _name = "yatmo.map.cache"
    _description = "Yatmo cache"
    _rec_name = "key"

    key = fields.Char(required=True, index=True)
    value = fields.Text(required=True)
    expires = fields.Datetime(required=True, index=True)

    _key_unique = models.Constraint("UNIQUE(key)", "The cache key must be unique.")

    @api.model
    def get_value(self, key):
        """Stored value of ``key``, or None when absent or expired."""
        record = self.sudo().search([("key", "=", key)], limit=1)
        if not record or record.expires < fields.Datetime.now():
            return None
        try:
            return json.loads(record.value)
        except ValueError:
            return None

    @api.model
    def set_value(self, key, value, ttl_seconds):
        """Stores ``value`` (JSON-serializable) under ``key`` for ``ttl_seconds``.

        An upsert: two page views of a new listing geocode the same address at the same time and
        both store it; a plain create would make the second one fail on the unique key."""
        now = fields.Datetime.now()
        self.env.cr.execute(
            """
            INSERT INTO yatmo_map_cache (key, value, expires, create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, expires = EXCLUDED.expires,
                write_uid = EXCLUDED.write_uid, write_date = EXCLUDED.write_date
            """,
            (key, json.dumps(value, ensure_ascii=False), now + timedelta(seconds=ttl_seconds),
             self.env.uid, now, self.env.uid, now),
        )
        self.invalidate_model()

    @api.model
    def _purge_expired(self):
        """Cron: removes the expired entries."""
        self.sudo().search([("expires", "<", fields.Datetime.now())]).unlink()

    @api.model
    def _clear_prefix(self, prefix):
        """Removes every entry whose key starts with ``prefix``."""
        self.sudo().search([("key", "=like", prefix + "%")]).unlink()
