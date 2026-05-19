# Documents bucket — raw uploaded files, utility bills, OCR inputs
resource "aws_s3_bucket" "documents" {
  bucket = "${var.name_prefix}-documents"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

# Object Lock for 7-year retention (SOC 2 + regulatory requirement)
resource "aws_s3_bucket_object_lock_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    default_retention {
      mode  = "GOVERNANCE"
      years = 7
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    id     = "archive-after-2-years"
    status = "Enabled"
    transition {
      days          = 730
      storage_class = "GLACIER_IR"
    }
  }
}

# Reports bucket — generated PDF/XML reports (signed, versioned)
resource "aws_s3_bucket" "reports" {
  bucket = "${var.name_prefix}-reports"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_object_lock_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    default_retention {
      mode  = "COMPLIANCE"  # Stronger: immutable for regulatory period
      years = 10
    }
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "documents_bucket" { value = aws_s3_bucket.documents.id }
output "reports_bucket"   { value = aws_s3_bucket.reports.id }
