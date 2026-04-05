/**
 * Terms of Service Page
 *
 * Required for Google OAuth approval and legal compliance.
 * Covers acceptable use, service terms, liability, and termination.
 *
 * Last Updated: 2026-04-04
 */

import theme from "../theme.js";

export default function TermsOfService({ onBack }) {
  const primaryColor = theme.colors.primary;
  const darkText = theme.colors.text.dark;
  const lightText = theme.colors.text.light;
  const lightBg = theme.colors.background.light;

  return (
    <div style={{
      minHeight: "100vh",
      background: theme.colors.background.gradient,
      fontFamily: "sans-serif"
    }}>
      {/* Header */}
      <header style={{
        padding: "20px 24px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        maxWidth: "900px",
        margin: "0 auto"
      }}>
        <div style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: 28,
          fontWeight: 700,
          color: darkText,
          display: "flex",
          alignItems: "center",
          gap: 8
        }}>
          <span style={{ fontSize: 32 }}>📄</span>
          Invoi
        </div>
        <button
          onClick={onBack || (() => window.history.back())}
          style={{
            padding: "8px 20px",
            background: "white",
            border: `2px solid ${primaryColor}`,
            borderRadius: 8,
            color: primaryColor,
            fontWeight: 600,
            fontSize: 14,
            cursor: "pointer",
            transition: "all 0.2s"
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = primaryColor;
            e.currentTarget.style.color = "white";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = "white";
            e.currentTarget.style.color = primaryColor;
          }}
        >
          ← Back
        </button>
      </header>

      {/* Content */}
      <main style={{
        maxWidth: "800px",
        margin: "0 auto",
        padding: "40px 24px 80px",
        background: "white",
        borderRadius: 16,
        marginTop: 20,
        marginBottom: 40,
        boxShadow: "0 2px 12px rgba(0, 0, 0, 0.08)"
      }}>
        <h1 style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: 42,
          fontWeight: 700,
          color: darkText,
          marginBottom: 12
        }}>
          Terms of Service
        </h1>
        <p style={{
          fontSize: 14,
          color: lightText,
          marginBottom: 40
        }}>
          Last Updated: April 4, 2026
        </p>

        <Section title="Agreement to Terms">
          <p>
            By accessing or using Invoi (the "Service"), you agree to be bound by these Terms of Service
            ("Terms"). If you do not agree to these Terms, you may not access or use the Service.
          </p>
          <p>
            We reserve the right to modify these Terms at any time. We will notify you of material changes
            by posting the updated Terms on this page. Your continued use of the Service after changes are
            posted constitutes acceptance of the new Terms.
          </p>
        </Section>

        <Section title="Description of Service">
          <p>
            Invoi is a web-based invoicing application designed for hourly 1099 contractors. The Service allows
            you to:
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Create and manage professional invoices</li>
            <li>Generate PDF invoices from customizable templates</li>
            <li>Send invoices via email to your clients</li>
            <li>Track invoice status (draft, sent, paid, overdue)</li>
            <li>Generate monthly reports for accounting purposes</li>
            <li>Store and manage client information</li>
            <li>Access additional features through paid subscription tiers (when available)</li>
          </ul>
        </Section>

        <Section title="Account Registration and Security">
          <p>
            To use Invoi, you must sign in with a valid Google account. You are responsible for:
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Maintaining the security of your Google account credentials</li>
            <li>All activities that occur under your account</li>
            <li>Ensuring the accuracy and completeness of information you provide</li>
            <li>Notifying us immediately of any unauthorized access or security breach</li>
          </ul>
          <p>
            You must be at least 18 years old to use the Service. You represent and warrant that all
            information you provide is accurate and current.
          </p>
        </Section>

        <Section title="Acceptable Use">
          <p>You agree to use the Service only for lawful purposes. You will not:</p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Use the Service to create fraudulent or misleading invoices</li>
            <li>Violate any applicable laws, regulations, or third-party rights</li>
            <li>Attempt to gain unauthorized access to the Service or related systems</li>
            <li>Interfere with or disrupt the integrity or performance of the Service</li>
            <li>Use the Service to transmit spam, malware, or harmful code</li>
            <li>Reverse engineer, decompile, or attempt to extract source code from the Service</li>
            <li>Use the Service in any manner that could damage, disable, or impair the Service</li>
            <li>Resell, redistribute, or provide access to the Service to third parties without authorization</li>
          </ul>
          <p>
            We reserve the right to suspend or terminate your account if you violate these acceptable use
            provisions.
          </p>
        </Section>

        <Section title="User Content and Data">
          <p>
            You retain all rights to the content you create using the Service, including invoices, service logs,
            and client information ("User Content"). By using the Service, you grant us a limited license to:
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Store and process your User Content to provide the Service</li>
            <li>Generate PDFs and deliver emails on your behalf</li>
            <li>Back up and maintain copies of your data for service reliability</li>
          </ul>
          <p>
            You are solely responsible for the accuracy, legality, and appropriateness of your User Content.
            You represent that you have the right to use and share all information you provide to the Service.
          </p>
          <p>
            We recommend you maintain your own backups of important data. While we implement industry-standard
            security measures, you acknowledge that no system is completely secure.
          </p>
        </Section>

        <Section title="Intellectual Property">
          <p>
            The Service, including its design, features, templates, and underlying technology, is owned by Invoi
            and protected by copyright, trademark, and other intellectual property laws. You are granted a limited,
            non-exclusive, non-transferable license to use the Service for its intended purpose.
          </p>
          <p>
            The invoice templates, themes, and design elements provided by the Service are licensed to you for
            use in generating invoices for your business. You may not extract, reuse, or redistribute these
            templates outside the Service.
          </p>
        </Section>

        <Section title="Payment and Subscriptions">
          <p>
            Invoi offers both free and paid subscription tiers (when available). The free tier includes limited
            features and usage quotas. Paid subscriptions unlock additional features and higher usage limits.
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Subscription fees are billed in advance on a monthly or annual basis</li>
            <li>All fees are non-refundable except as required by law</li>
            <li>We reserve the right to change pricing with 30 days' notice</li>
            <li>Failure to pay subscription fees may result in service suspension or termination</li>
            <li>You may cancel your subscription at any time through your account settings</li>
          </ul>
          <p>
            When paid subscriptions are available, you will provide payment information through our secure payment
            processor. We do not store your full credit card details.
          </p>
        </Section>

        <Section title="Service Availability and Modifications">
          <p>
            We strive to provide reliable, uninterrupted access to the Service, but we do not guarantee that the
            Service will be available at all times. The Service may be temporarily unavailable due to:
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Scheduled or emergency maintenance</li>
            <li>Technical issues or outages</li>
            <li>Circumstances beyond our reasonable control</li>
          </ul>
          <p>
            We reserve the right to modify, suspend, or discontinue any aspect of the Service at any time, with
            or without notice. We are not liable for any modification, suspension, or discontinuation of the Service.
          </p>
        </Section>

        <Section title="Third-Party Services">
          <p>
            The Service integrates with third-party services, including:
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Google (for authentication via OAuth)</li>
            <li>Amazon Web Services (for hosting and storage)</li>
            <li>Email delivery services (for sending invoices)</li>
          </ul>
          <p>
            Your use of these third-party services is subject to their respective terms of service and privacy
            policies. We are not responsible for the practices or performance of third-party services.
          </p>
        </Section>

        <Section title="Limitation of Liability">
          <p>
            TO THE MAXIMUM EXTENT PERMITTED BY LAW, INVOI AND ITS AFFILIATES, OFFICERS, EMPLOYEES, AND AGENTS
            WILL NOT BE LIABLE FOR:
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Any indirect, incidental, special, consequential, or punitive damages</li>
            <li>Loss of profits, revenue, data, or business opportunities</li>
            <li>Service interruptions or data loss</li>
            <li>Errors or inaccuracies in invoices or reports generated by the Service</li>
            <li>Actions taken by you based on information provided by the Service</li>
          </ul>
          <p>
            OUR TOTAL LIABILITY FOR ANY CLAIMS ARISING FROM YOUR USE OF THE SERVICE WILL NOT EXCEED THE AMOUNT
            YOU PAID US IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM, OR $100, WHICHEVER IS GREATER.
          </p>
          <p>
            You acknowledge that you are solely responsible for ensuring the accuracy of invoices you send to
            clients and for compliance with applicable tax and business regulations.
          </p>
        </Section>

        <Section title="Indemnification">
          <p>
            You agree to indemnify, defend, and hold harmless Invoi and its affiliates from any claims, damages,
            losses, liabilities, and expenses (including reasonable attorneys' fees) arising from:
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Your use or misuse of the Service</li>
            <li>Your violation of these Terms</li>
            <li>Your violation of any rights of another party</li>
            <li>Your User Content or any information you provide</li>
          </ul>
        </Section>

        <Section title="Termination">
          <p>
            You may terminate your account at any time by contacting us at <a href="mailto:privacy@goinvoi.com" style={{ color: primaryColor, textDecoration: "none", fontWeight: 600 }}>privacy@goinvoi.com</a>.
            Upon termination:
          </p>
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>Your access to the Service will be revoked</li>
            <li>You may request a copy of your data within 30 days of termination</li>
            <li>We will delete your data in accordance with our Privacy Policy</li>
            <li>Fees paid prior to termination are non-refundable</li>
          </ul>
          <p>
            We reserve the right to suspend or terminate your account at any time if you violate these Terms
            or engage in conduct we deem harmful to the Service or other users.
          </p>
        </Section>

        <Section title="Disclaimer of Warranties">
          <p>
            THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS
            OR IMPLIED, INCLUDING BUT NOT LIMITED TO IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
            PARTICULAR PURPOSE, AND NON-INFRINGEMENT.
          </p>
          <p>
            WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR COMPLETELY SECURE. WE DO
            NOT PROVIDE LEGAL, TAX, OR ACCOUNTING ADVICE. YOU ARE RESPONSIBLE FOR ENSURING YOUR INVOICES AND
            BUSINESS PRACTICES COMPLY WITH APPLICABLE LAWS.
          </p>
        </Section>

        <Section title="Governing Law and Disputes">
          <p>
            These Terms are governed by the laws of the United States and the State of Colorado, without regard
            to conflict of law principles. Any disputes arising from these Terms or your use of the Service will
            be resolved through binding arbitration in accordance with the rules of the American Arbitration
            Association, except that either party may seek injunctive relief in court.
          </p>
          <p>
            You waive any right to participate in class actions or class-wide arbitration.
          </p>
        </Section>

        <Section title="General Provisions">
          <ul style={{ marginLeft: 24, lineHeight: 1.8 }}>
            <li>
              <strong>Entire Agreement:</strong> These Terms, together with our Privacy Policy, constitute
              the entire agreement between you and Invoi regarding the Service
            </li>
            <li>
              <strong>Severability:</strong> If any provision of these Terms is found invalid or unenforceable,
              the remaining provisions will remain in full effect
            </li>
            <li>
              <strong>Waiver:</strong> Our failure to enforce any right or provision of these Terms does not
              constitute a waiver of that right or provision
            </li>
            <li>
              <strong>Assignment:</strong> You may not assign or transfer these Terms or your account without
              our prior written consent. We may assign these Terms without restriction
            </li>
          </ul>
        </Section>

        <Section title="Contact Us">
          <p>
            If you have questions or concerns about these Terms of Service, please contact us:
          </p>
          <p style={{ marginTop: 16, padding: 16, background: lightBg, borderRadius: 8, border: "2px solid #f0dce0" }}>
            <strong>Email:</strong> <a href="mailto:privacy@goinvoi.com" style={{ color: primaryColor, textDecoration: "none", fontWeight: 600 }}>privacy@goinvoi.com</a><br />
            <strong>Subject Line:</strong> Terms of Service Inquiry - Invoi
          </p>
          <p style={{ marginTop: 20, fontSize: 14, color: lightText, fontStyle: "italic" }}>
            Note: This terms of service template is provided for informational purposes. We recommend consulting
            with a qualified attorney to ensure compliance with all applicable laws and regulations.
          </p>
        </Section>
      </main>

      {/* Footer */}
      <footer style={{
        padding: "40px 24px",
        textAlign: "center",
        color: lightText,
        fontSize: 14
      }}>
        <div style={{
          maxWidth: "800px",
          margin: "0 auto"
        }}>
          <div style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: 20,
            fontWeight: 700,
            color: darkText,
            marginBottom: 12
          }}>Invoi</div>
          <div style={{ marginBottom: 8 }}>Invoicing for hourly contractors</div>
          <div>© 2026 Invoi. Built for people who work by the hour.</div>
        </div>
      </footer>
    </div>
  );
}

// Reusable section component for consistent styling
function Section({ title, children }) {
  const darkText = "#2c1810";
  const mediumText = "#6a4a40";

  return (
    <section style={{ marginBottom: 40 }}>
      <h2 style={{
        fontFamily: "'Playfair Display', serif",
        fontSize: 26,
        fontWeight: 700,
        color: darkText,
        marginBottom: 16,
        paddingBottom: 8,
        borderBottom: "2px solid #f0dce0"
      }}>
        {title}
      </h2>
      <div style={{
        fontSize: 16,
        lineHeight: 1.8,
        color: mediumText
      }}>
        {children}
      </div>
    </section>
  );
}
