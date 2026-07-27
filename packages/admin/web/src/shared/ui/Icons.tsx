import type { ReactElement, ReactNode, SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

function I({ children, ...rest }: P & { children: ReactNode }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...rest}
    >
      {children}
    </svg>
  );
}

export const IconLayout = (p: P) => (
  <I {...p}>
    <rect x="3" y="3" width="7" height="9" rx="1" />
    <rect x="14" y="3" width="7" height="5" rx="1" />
    <rect x="14" y="12" width="7" height="9" rx="1" />
    <rect x="3" y="16" width="7" height="5" rx="1" />
  </I>
);
export const IconTable = (p: P) => (
  <I {...p}>
    <path d="M3 5h18v14H3z" />
    <path d="M3 10h18M9 5v14" />
  </I>
);
export const IconImage = (p: P) => (
  <I {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <circle cx="9" cy="10" r="1.5" />
    <path d="M3 16l5-4 4 3 4-5 5 6" />
  </I>
);
export const IconSettings = (p: P) => (
  <I {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3v2M12 19v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M3 12h2M19 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </I>
);
export const IconPlus = (p: P) => (
  <I {...p}>
    <path d="M12 5v14M5 12h14" />
  </I>
);
export const IconMore = (p: P) => (
  <I {...p}>
    <circle cx="6" cy="12" r="1.2" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
    <circle cx="18" cy="12" r="1.2" fill="currentColor" stroke="none" />
  </I>
);
export const IconX = (p: P) => (
  <I {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </I>
);
export const IconPanel = (p: P) => (
  <I {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M9 4v16" />
  </I>
);
export const IconUsers = (p: P) => (
  <I {...p}>
    <circle cx="9" cy="8" r="3" />
    <path d="M3 19c0-3 2.5-5 6-5s6 2 6 5" />
    <circle cx="17" cy="9" r="2.5" />
    <path d="M21 19c0-2.2-1.5-3.8-4-4.2" />
  </I>
);
export const IconBuilding = (p: P) => (
  <I {...p}>
    <path d="M4 20V6l8-3 8 3v14" />
    <path d="M9 20v-6h6v6M9 10h.01M15 10h.01M9 14h.01M15 14h.01" />
  </I>
);
export const IconFile = (p: P) => (
  <I {...p}>
    <path d="M7 3h7l5 5v13H7z" />
    <path d="M14 3v5h5M10 13h6M10 17h4" />
  </I>
);
export const IconTag = (p: P) => (
  <I {...p}>
    <path d="M3 12V4h8l9 9-8 8-9-9z" />
    <circle cx="8.5" cy="8.5" r="1.2" fill="currentColor" stroke="none" />
  </I>
);
export const IconChat = (p: P) => (
  <I {...p}>
    <path d="M5 5h14a2 2 0 012 2v8a2 2 0 01-2 2H9l-4 3v-3H5a2 2 0 01-2-2V7a2 2 0 012-2z" />
  </I>
);
export const IconFolder = (p: P) => (
  <I {...p}>
    <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
  </I>
);
export const IconInvoice = (p: P) => (
  <I {...p}>
    <path d="M7 3h10v18l-2.5-1.5L12 21l-2.5-1.5L7 21z" />
    <path d="M10 9h4M10 13h4" />
  </I>
);
export const IconShield = (p: P) => (
  <I {...p}>
    <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" />
  </I>
);
export const IconDatabase = (p: P) => (
  <I {...p}>
    <ellipse cx="12" cy="6" rx="7" ry="3" />
    <path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
    <path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" />
  </I>
);
export const IconKey = (p: P) => (
  <I {...p}>
    <circle cx="8" cy="14" r="3" />
    <path d="M10.5 12.5L20 3M16 3h4v4" />
  </I>
);
export const IconSun = (p: P) => (
  <I {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </I>
);
export const IconMoon = (p: P) => (
  <I {...p}>
    <path d="M20 14.5A7.5 7.5 0 119.5 4 6 6 0 0020 14.5z" />
  </I>
);
export const IconMonitor = (p: P) => (
  <I {...p}>
    <rect x="3" y="4" width="18" height="12" rx="2" />
    <path d="M8 20h8M12 16v4" />
  </I>
);
export const IconChevronLeft = (p: P) => (
  <I {...p}>
    <path d="M14 6l-6 6 6 6" />
  </I>
);
export const IconChevronRight = (p: P) => (
  <I {...p}>
    <path d="M10 6l6 6-6 6" />
  </I>
);
export const IconBox = (p: P) => (
  <I {...p}>
    <path d="M3 8l9-4 9 4-9 4-9-4z" />
    <path d="M3 8v8l9 4 9-4V8M12 12v8" />
  </I>
);
export const IconLink = (p: P) => (
  <I {...p}>
    <path d="M10 13a5 5 0 007.07 0l2.12-2.12a5 5 0 00-7.07-7.07L10.5 5.5" />
    <path d="M14 11a5 5 0 00-7.07 0L4.8 13.12a5 5 0 007.07 7.07L13.5 18.5" />
  </I>
);
export const IconMail = (p: P) => (
  <I {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 7l9 7 9-7" />
  </I>
);
export const IconCalendar = (p: P) => (
  <I {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M8 3v4M16 3v4M3 11h18" />
  </I>
);
export const IconClock = (p: P) => (
  <I {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v6l4 2" />
  </I>
);
export const IconCart = (p: P) => (
  <I {...p}>
    <path d="M4 5h2l2.5 11h9.5l2-8H8" />
    <circle cx="10" cy="20" r="1.2" fill="currentColor" stroke="none" />
    <circle cx="17" cy="20" r="1.2" fill="currentColor" stroke="none" />
  </I>
);
export const IconPackage = (p: P) => (
  <I {...p}>
    <path d="M3 8l9-4 9 4v9l-9 4-9-4V8z" />
    <path d="M12 12v9M3 8l9 4 9-4" />
  </I>
);
export const IconGlobe = (p: P) => (
  <I {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3c2.5 2.8 4 6 4 9s-1.5 6.2-4 9c-2.5-2.8-4-6-4-9s1.5-6.2 4-9z" />
  </I>
);
export const IconMapPin = (p: P) => (
  <I {...p}>
    <path d="M12 21s7-5.5 7-11a7 7 0 10-14 0c0 5.5 7 11 7 11z" />
    <circle cx="12" cy="10" r="2.5" />
  </I>
);
export const IconChart = (p: P) => (
  <I {...p}>
    <path d="M4 19V5M4 19h16" />
    <path d="M8 16v-5M12 16V8M16 16v-3M20 16v-8" />
  </I>
);
export const IconBell = (p: P) => (
  <I {...p}>
    <path d="M6 9a6 6 0 0112 0c0 7 3 7 3 7H3s3 0 3-7" />
    <path d="M10 20a2 2 0 004 0" />
  </I>
);
export const IconStar = (p: P) => (
  <I {...p}>
    <path d="M12 3l2.4 5.4L20 9.3l-4 4.2 1 6L12 16.8 7 19.5l1-6-4-4.2 5.6-.9L12 3z" />
  </I>
);
export const IconHeart = (p: P) => (
  <I {...p}>
    <path d="M12 20s-7-4.4-7-9.5A4.5 4.5 0 0112 7a4.5 4.5 0 017 3.5C19 15.6 12 20 12 20z" />
  </I>
);
export const IconZap = (p: P) => (
  <I {...p}>
    <path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" />
  </I>
);
export const IconLayers = (p: P) => (
  <I {...p}>
    <path d="M12 3l9 5-9 5-9-5 9-5z" />
    <path d="M3 12l9 5 9-5M3 16l9 5 9-5" />
  </I>
);
export const IconCode = (p: P) => (
  <I {...p}>
    <path d="M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14" />
  </I>
);
export const IconHash = (p: P) => (
  <I {...p}>
    <path d="M5 9h14M5 15h14M10 3L8 21M16 3l-2 18" />
  </I>
);
export const IconBookmark = (p: P) => (
  <I {...p}>
    <path d="M7 4h10a1 1 0 011 1v16l-6-3.5L6 21V5a1 1 0 011-1z" />
  </I>
);
export const IconTruck = (p: P) => (
  <I {...p}>
    <path d="M3 7h11v10H3zM14 10h4l3 3v4h-7V10z" />
    <circle cx="7" cy="18" r="1.5" />
    <circle cx="17" cy="18" r="1.5" />
  </I>
);
export const IconPhone = (p: P) => (
  <I {...p}>
    <rect x="7" y="2" width="10" height="20" rx="2" />
    <path d="M11 18h2" />
  </I>
);
export const IconSpark = (p: P) => (
  <I {...p}>
    <path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8" />
    <circle cx="12" cy="12" r="3" />
  </I>
);
export const IconLock = (p: P) => (
  <I {...p}>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V8a4 4 0 018 0v3" />
  </I>
);
export const IconFingerprint = (p: P) => (
  <I {...p}>
    <path d="M7 11a5 5 0 0110 0v3a2 2 0 01-4 0v-2" />
    <path d="M12 11v6a1 1 0 01-2 0" />
    <path d="M6 14v1a6 6 0 0012 0v-1" />
  </I>
);
export const IconList = (p: P) => (
  <I {...p}>
    <path d="M9 7h11M9 12h11M9 17h11M5 7h.01M5 12h.01M5 17h.01" />
  </I>
);
export const IconActivity = (p: P) => (
  <I {...p}>
    <path d="M3 12h4l2-7 4 14 2-7h6" />
  </I>
);
export const IconFlag = (p: P) => (
  <I {...p}>
    <path d="M5 21V4h11l-1.5 4L18 12H5" />
  </I>
);
export const IconBook = (p: P) => (
  <I {...p}>
    <path d="M4 5a2 2 0 012-2h12v18H6a2 2 0 01-2-2V5z" />
    <path d="M8 7h8M8 11h8M8 15h5" />
  </I>
);
export const IconBriefcase = (p: P) => (
  <I {...p}>
    <rect x="3" y="8" width="18" height="12" rx="2" />
    <path d="M9 8V6a2 2 0 012-2h2a2 2 0 012 2v2M3 13h18" />
  </I>
);
export const IconWallet = (p: P) => (
  <I {...p}>
    <path d="M3 8h16a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z" />
    <path d="M3 8V6a2 2 0 012-2h12M17 14h.01" />
  </I>
);
export const IconTicket = (p: P) => (
  <I {...p}>
    <path d="M3 9a2 2 0 012-2h14a2 2 0 012 2v2a2 2 0 000 4v2a2 2 0 01-2 2H5a2 2 0 01-2-2v-2a2 2 0 000-4V9z" />
    <path d="M12 7v10" />
  </I>
);
export const IconGift = (p: P) => (
  <I {...p}>
    <rect x="4" y="10" width="16" height="11" rx="1" />
    <path d="M12 10v11M4 14h16M8 10c0-2 1.5-4 4-4s4 2 4 4" />
  </I>
);
export const IconHome = (p: P) => (
  <I {...p}>
    <path d="M4 11l8-7 8 7v9a1 1 0 01-1 1h-5v-6H10v6H5a1 1 0 01-1-1v-9z" />
  </I>
);
export const IconPercent = (p: P) => (
  <I {...p}>
    <path d="M19 5L5 19" />
    <circle cx="7.5" cy="7.5" r="2.5" />
    <circle cx="16.5" cy="16.5" r="2.5" />
  </I>
);
export const IconMegaphone = (p: P) => (
  <I {...p}>
    <path d="M4 11v2a2 2 0 002 2h1l4 4V5L7 9H6a2 2 0 00-2 2z" />
    <path d="M15 9.5a4 4 0 010 5M18 7a7 7 0 010 10" />
  </I>
);

type IconFn = (p: P) => ReactElement;

/**
 * Map resource / table API names → icons for AdminBoard nav.
 * First match wins — keep specific patterns above generic ones.
 * Covers ecommerce, marketplace, SaaS, CRM, LMS, social, fintech, support, CMS, …
 */
export function resourceNavIcon(name: string): IconFn {
  const n = name
    .toLowerCase()
    .replace(/[.\s-]+/g, "_")
    .replace(/_?(tbl|table|model|entity|records?)_?/g, "_")
    .replace(/^_+|_+$/g, "");

  // ── Auth / identity / security ─────────────────────────────────
  if (/mfa|totp|webauthn|passkey|fingerprint|2fa/.test(n)) return IconFingerprint;
  if (/oauth|openid|social_login|identity_provider|sso_provider/.test(n)) return IconGlobe;
  if (/session|refresh_token|access_token_store/.test(n)) return IconClock;
  if (/api.?key|apikey|service_account/.test(n)) return IconKey;
  if (/password|credential|vault|secret|encryption_key/.test(n)) return IconLock;
  if (/permission|acl|rbac|policy|grant|scope/.test(n)) return IconLock;
  if (/\brole\b|user_role|group_role|group(?!on)/.test(n)) return IconShield;
  if (/audit|activity_log|event_log|access_log|changelog|history/.test(n))
    return IconActivity;
  if (/auth|security|sso|login_attempt|ban|blocklist|allowlist|blacklist|whitelist/.test(n))
    return IconShield;

  // ── Join / M2M tables (before "member"/"user") ─────────────────
  if (
    /membership|member_of|join_table|through|m2m|_x_|_link$|junction|pivot|_map$|user_group|group_user|post_tag|tag_post|product_category|order_item|line_item|cart_item|wishlist_item|project_member|team_member|course_student|enrollment/.test(
      n,
    )
  )
    return IconLink;

  // ── Ecommerce / marketplace ────────────────────────────────────
  if (/coupon|promo|voucher|discount|deal_code|gift.?card|loyalty/.test(n))
    return IconPercent;
  if (/gift|reward|referral_reward/.test(n)) return IconGift;
  if (
    /invoice|bill|receipt|payment|charge|payout|refund|transaction|transfer|settlement|ledger|wallet|balance|escrow|tax_line|tax_rate/.test(
      n,
    )
  )
    return IconInvoice;
  if (/subscription|plan|pricing|tier|entitlement|license|seat/.test(n))
    return IconWallet;
  if (/order|checkout|purchase|sale|sales_order|purchase_order|po_/.test(n))
    return IconCart;
  if (/cart|basket|bag|wishlist|saved_for_later/.test(n)) return IconCart;
  if (
    /product|sku|variant|catalog|inventory|stock|warehouse|listing|merchandise|goods|bundle_product|offer/.test(
      n,
    )
  )
    return IconPackage;
  if (
    /ship|shipment|shipping|delivery|fulfill|carrier|parcel|consignment|logistics|tracking|return_request|rma/.test(
      n,
    )
  )
    return IconTruck;
  if (/warehouse|fulfillment_center|bin_location|shelf/.test(n)) return IconBox;
  if (/vendor|seller|merchant|supplier|storefront|shop|store(?!age)/.test(n))
    return IconBuilding;
  if (/price|pricing_rule|price_list|currency|fx_rate|exchange_rate/.test(n))
    return IconChart;
  if (/review|rating|testimonial|feedback/.test(n)) return IconStar;

  // ── CRM / sales / support ──────────────────────────────────────
  if (/lead|prospect|opportunity|pipeline_deal|deal(?!_code)|crm_/.test(n))
    return IconBriefcase;
  if (/account|company_account|sales_account/.test(n) && !/auth|user|session/.test(n))
    return IconBuilding;
  if (/contact|person|lead_contact/.test(n)) return IconUsers;
  if (/ticket|case|support|helpdesk|incident|sla|conversation/.test(n))
    return IconTicket;
  if (/campaign|newsletter|broadcast|announcement|megaphone|ad_|ads_|advert/.test(n))
    return IconMegaphone;
  if (/pipeline|funnel|stage|kanban/.test(n)) return IconLayers;
  if (/quote|proposal|estimate|contract|agreement/.test(n)) return IconFile;

  // ── LMS / education / content courses ──────────────────────────
  if (
    /course|lesson|module_lesson|curriculum|syllabus|class(room)?|lecture|quiz|exam|assignment|homework|grade|score_card|certificate|enrollment|student|teacher|instructor|cohort|learning|lms_/.test(
      n,
    )
  )
    return IconBook;

  // ── Social / community / UGC ───────────────────────────────────
  if (/follow|follower|friend|connection|block|mute/.test(n)) return IconUsers;
  if (/like|heart|love|reaction|clap|upvote|downvote|vote/.test(n)) return IconHeart;
  if (/feed|timeline|activity_stream|notification|notif|alert|push|bell/.test(n))
    return IconBell;
  if (/story|reel|status_update|moment/.test(n)) return IconSpark;
  if (/dm|direct_message|chat_room|channel|thread|inbox|outbox/.test(n))
    return IconChat;
  if (/comment|reply|discussion|forum_post/.test(n)) return IconChat;
  if (/post|article|blog|tweet|thread_post|publication/.test(n)) return IconFile;
  if (/hashtag|mention|tag|label|categor|topic|topic|genre/.test(n)) return IconTag;
  if (/bookmark|favorite|starred|save_later|reading_list/.test(n)) return IconBookmark;
  if (/report|flag|moderation|abuse/.test(n)) return IconFlag;
  if (/poll|survey|questionnaire/.test(n)) return IconList;

  // ── CMS / content / knowledge ──────────────────────────────────
  if (
    /page|cms_|content_block|section|widget|menu_item|navigation|nav_item|seo_|meta_tag|redirect|slug_map/.test(
      n,
    )
  )
    return IconFile;
  if (/wiki|knowledge|kb_|faq|help_article|doc|document|note|snippet/.test(n))
    return IconBook;
  if (/media|asset|image|photo|gallery|video|audio|upload|attachment|blob|file_object/.test(n))
    return IconImage;
  if (/template|layout|theme_pack|partial/.test(n)) return IconLayers;

  // ── SaaS / product / feature flags ─────────────────────────────
  if (/feature.?flag|experiment|ab_test|variant_test|rollout/.test(n)) return IconFlag;
  if (/tenant|workspace|organization|org|company|department|division|team|squad|club/.test(n))
    return IconBuilding;
  if (/invitation|invite|onboarding|waitlist|signup/.test(n)) return IconMail;
  if (/usage|quota|limit|meter|billing_metric/.test(n)) return IconChart;
  if (/integration|connector|plugin|addon|extension|app_install/.test(n))
    return IconLayers;
  if (/webhook|endpoint|callback|hook/.test(n)) return IconZap;
  if (/(^|_)api(_|$)|route|service|microservice/.test(n) && !/api.?key|apikey/.test(n))
    return IconCode;


  // ── People (generic — after membership/CRM specifics) ──────────
  if (
    /user|people|person|staff|employee|customer|client|profile|member(?!ship)|subscriber|patient|doctor|agent|admin_user|superuser|author|owner/.test(
      n,
    )
  )
    return IconUsers;

  // ── Project / work management ──────────────────────────────────
  if (
    /project|board|sprint|epic|story_point|milestone|roadmap|initiative|portfolio/.test(
      n,
    )
  )
    return IconFolder;
  if (/task|todo|checklist|subtask|work_item|issue|bug|ticket_item/.test(n))
    return IconList;
  if (/time_entry|timesheet|timer|clock_in/.test(n)) return IconClock;
  if (/folder|directory|namespace|space(?!x)/.test(n)) return IconFolder;

  // ── Booking / travel / hospitality ─────────────────────────────
  if (
    /booking|reservation|appointment|slot|availability|calendar|schedule|event|meeting|room|hotel|flight|itinerary|guest|stay|listing_stay/.test(
      n,
    )
  )
    return IconCalendar;
  if (/ticket_event|venue|seat|show|concert/.test(n)) return IconTicket;
  if (/property|listing|home|rental|airbnb|apartment/.test(n)) return IconHome;

  // ── Fintech / banking ──────────────────────────────────────────
  if (
    /wallet|balance|ledger|journal|bank|card|iban|account_balance|crypto|coin|portfolio|holding|trade|order_book|position/.test(
      n,
    )
  )
    return IconWallet;
  if (/loan|mortgage|credit|debit|kyc|aml|compliance/.test(n)) return IconBriefcase;

  // ── Healthcare ─────────────────────────────────────────────────
  if (
    /patient|doctor|physician|clinic|hospital|prescription|medication|lab|appointment_medical|encounter|diagnosis|insurance_claim/.test(
      n,
    )
  )
    return IconActivity;
  if (/pharmacy|drug|dose/.test(n)) return IconPackage;

  // ── Real estate / map ──────────────────────────────────────────
  if (/address|location|place|city|geo|coordinate|map|pin|region|zone|district|neighborhood/.test(n))
    return IconMapPin;
  if (/country|state_province|locale|language|i18n|translation|currency_country/.test(n))
    return IconGlobe;

  // ── Comms ──────────────────────────────────────────────────────
  if (/email|mail|newsletter|smtp|message_log/.test(n)) return IconMail;
  if (/phone|sms|call|voip|mobile_number|device_token/.test(n)) return IconPhone;
  if (/comment|message|chat/.test(n)) return IconChat;

  // ── Analytics / growth ─────────────────────────────────────────
  if (
    /metric|stat|analytic|report|dashboard|kpi|chart|revenue|mrr|arr|funnel|cohort|conversion|impression|click|pageview|session_event|track/.test(
      n,
    )
  )
    return IconChart;
  if (/score|rating|nps|csat/.test(n)) return IconStar;

  // ── Infra / jobs / data ────────────────────────────────────────
  if (/db|schema|migration|registry|fixture|seed/.test(n)) return IconDatabase;
  if (/job|worker|queue|cron|celery|task_run|batch|pipeline|etl|import|export/.test(n))
    return IconZap;
  if (/layer|stack|module|plugin|package|bundle|release|version|deploy/.test(n))
    return IconLayers;
  if (/code|snippet|script|template_code|workflow|automation/.test(n)) return IconCode;
  if (/hash|slug|token_map|id_map|uuid_map/.test(n)) return IconHash;
  if (/ai|ml|model_run|prompt|embedding|vector|llm|inference/.test(n)) return IconSpark;
  if (/box|parcel|package(?!_json)/.test(n)) return IconPackage;
  if (/setting|config|pref|option|site_setting|app_config/.test(n)) return IconSettings;
  if (/collection|catalog_list|playlist|queue_list/.test(n)) return IconList;
  if (/home|landing|site/.test(n)) return IconHome;

  // Fallback: varied pleasant pool (stable hash)
  const pool: IconFn[] = [
    IconBox,
    IconSpark,
    IconLayers,
    IconStar,
    IconZap,
    IconGlobe,
    IconFolder,
    IconFile,
    IconTag,
    IconUsers,
    IconChart,
    IconBookmark,
    IconList,
    IconActivity,
    IconBriefcase,
    IconBook,
    IconGift,
    IconHome,
    IconTicket,
    IconTable,
  ];
  let h = 0;
  for (let i = 0; i < n.length; i++) h = (h * 31 + n.charCodeAt(i)) >>> 0;
  return pool[h % pool.length]!;
}
