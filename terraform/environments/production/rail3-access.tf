# Opt in only after the three hostname/path Access applications exist.
variable "rail3_access" {
  description = "Cloudflare Access settings for the TigerEye Rail 3 custom domains."
  type = object({
    issuer                 = string
    web_audience           = string
    control_audience       = string
    webhook_audience       = string
    webhook_path           = string
    control_plane_hostname = string
  })
  default = null

  validation {
    condition = var.rail3_access == null ? true : (
      can(regex("^https://[a-z0-9-]+[.]cloudflareaccess[.]com$", var.rail3_access.issuer)) &&
      alltrue([for aud in [var.rail3_access.web_audience, var.rail3_access.control_audience, var.rail3_access.webhook_audience] : can(regex("^[0-9a-f]{64}$", aud))]) &&
      length(distinct([var.rail3_access.web_audience, var.rail3_access.control_audience, var.rail3_access.webhook_audience])) == 3 &&
      can(regex("^/webhooks/automation/[A-Za-z0-9_-]+$", var.rail3_access.webhook_path)) &&
      can(regex("^[a-z0-9-]+([.][a-z0-9-]+)+$", var.rail3_access.control_plane_hostname)) &&
      !endswith(var.rail3_access.control_plane_hostname, ".workers.dev")
    )
    error_message = "Rail 3 requires an Access team issuer, three distinct AUD tags, an exact automation webhook path and a custom control-plane hostname."
  }
}

variable "rail3_access_sidecar_image_id" {
  description = "Verified prebuilt Modal image ID for the Rail 3 Access sidecar."
  type        = string
  default     = ""
}

resource "terraform_data" "rail3_ingress" {
  count = var.rail3_access == null ? 0 : 1

  lifecycle {
    precondition {
      condition = (
        local.web_custom_domain_enabled &&
        var.sandbox_provider == "modal-vm" &&
        can(regex("^im-[A-Za-z0-9]+$", var.rail3_access_sidecar_image_id)) &&
        !endswith(lower(local.web_custom_domain), ".workers.dev") &&
        lower(local.web_custom_domain) != var.rail3_access.control_plane_hostname
      )
      error_message = "Rail 3 requires two distinct Cloudflare custom domains, the Modal VM backend and a verified Access sidecar image ID."
    }
  }
}
