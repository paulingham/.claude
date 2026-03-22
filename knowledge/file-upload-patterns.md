# File Upload Patterns

## Storage Strategy

| Strategy | When | Tradeoffs |
|----------|------|-----------|
| Direct-to-cloud (presigned URL) | Production, large files | Best UX, complex setup |
| Server-side upload | Small files, simple apps | Simple, uses server memory/bandwidth |
| Chunked/multipart | Files > 100MB | Resume support, progress tracking |

**Never** store uploads on the local filesystem in production (breaks with multiple instances, lost on redeploy).

## Direct-to-Cloud Upload (Recommended)

```
1. Client requests upload URL from API (POST /api/uploads, { filename, content_type, size })
2. Server validates: allowed type? size within limits? user authorized?
3. Server generates presigned URL (S3 PutObject, GCS SignedUrl, Azure SAS)
4. Server returns { upload_url, file_key } to client
5. Client uploads directly to cloud storage using presigned URL
6. Client notifies API of completion (PATCH /api/uploads/:id, { status: "completed" })
7. Server verifies file exists in storage, processes (thumbnails, virus scan)
```

### Presigned URL Generation

**AWS S3:**
```javascript
const url = await s3.getSignedUrl('putObject', {
  Bucket: 'my-bucket',
  Key: `uploads/${userId}/${uuid}/${filename}`,
  ContentType: contentType,
  Expires: 300, // 5 minutes
});
```

**Google Cloud Storage:**
```python
blob = bucket.blob(f"uploads/{user_id}/{uuid}/{filename}")
url = blob.generate_signed_url(expiration=timedelta(minutes=5), method="PUT")
```

## File Validation

### At Request Time (before presigned URL)
```
- Content-Type: allowlist only (e.g., image/jpeg, image/png, application/pdf)
- File size: enforce maximum (e.g., 10MB for images, 100MB for documents)
- Filename: sanitize (strip path separators, special chars, limit length)
```

### After Upload (server-side verification)
```
- Verify Content-Type matches actual file content (magic bytes, not just extension)
- Re-check file size from storage metadata
- Virus scan (ClamAV, VirusTotal API, AWS GuardDuty)
- Image validation: verify dimensions, strip EXIF metadata (privacy)
```

**Never trust client-side validation alone.** Always re-validate server-side.

## Image Processing

```
On upload completion:
1. Generate thumbnails (150x150, 300x300, 600x600)
2. Convert to WebP/AVIF for web delivery
3. Strip EXIF metadata (contains GPS, camera info — PII)
4. Store originals separately from processed versions

Tools: Sharp (Node.js), ImageMagick/Vips (Rails/Python/Go)
Processing: async via background job (never in the request cycle)
```

## Storage Organization

```
Tenant-scoped paths (multi-tenant safety):
  {bucket}/{tenant_id}/uploads/{year}/{month}/{uuid}/{filename}

Never allow user-controlled paths — construct paths server-side using UUIDs.
```

## Serving Files

| Access Level | Method |
|-------------|--------|
| Public (avatars, product images) | CDN with public URL |
| Private (documents, exports) | Signed URL with expiry (15 min - 1 hour) |
| Sensitive (medical, legal) | Signed URL with very short expiry (5 min), audit logging |

## Cleanup

```
Orphaned uploads: files uploaded but never attached to a record
Strategy: background job runs daily, deletes uploads > 24h old with no record association
Deleted records: when a record with attachments is deleted, queue cleanup job for associated files
```

## Security Checklist

- [ ] Content-Type allowlist (not blocklist)
- [ ] File size limits enforced server-side
- [ ] Filename sanitized (no path traversal: `../../../etc/passwd`)
- [ ] File content verified (magic bytes match declared type)
- [ ] Virus scanning on upload
- [ ] EXIF metadata stripped from images
- [ ] Storage paths use UUIDs (not user-supplied filenames)
- [ ] Private files served via signed URLs (not direct public access)
- [ ] Upload endpoint rate-limited
- [ ] Storage bucket has no public read policy (unless intentionally public)
