-- One edition per user per day (excluding failed attempts, which can be retried).
CREATE UNIQUE INDEX idx_delivery_unique_edition
  ON delivery_history (user_id, edition_date)
  WHERE status != 'failed';
