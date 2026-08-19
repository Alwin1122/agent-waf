terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state requires a pre-existing S3 bucket and DynamoDB lock table.
  # Bootstrap those resources separately, then uncomment and configure:
  #
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "agent-waf/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "your-terraform-lock-table"
  # }
}
