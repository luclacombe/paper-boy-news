-- Storage RLS: users can only access EPUBs in their own folder ({user_id}/*)
-- The storage path convention is: {auth.uid()}/{filename}.epub

CREATE POLICY "Users upload own EPUBs"
  ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'epubs'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

CREATE POLICY "Users read own EPUBs"
  ON storage.objects FOR SELECT
  USING (
    bucket_id = 'epubs'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

CREATE POLICY "Users update own EPUBs"
  ON storage.objects FOR UPDATE
  USING (
    bucket_id = 'epubs'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

CREATE POLICY "Users delete own EPUBs"
  ON storage.objects FOR DELETE
  USING (
    bucket_id = 'epubs'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );
