import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import {
  AppNav, Card, CardHeader, CardBody, FieldGroup,
  Input, Select, Textarea, Btn, Alert, Divider,
  SectionLabel, Badge, formatINR, fmtMs,
} from '../components/Primitives';
import RagQualityGate from '../components/RagQualityGate';

// Validation
function validate(f) {
  const errs = {};
  if (!f.loan_type) errs.loan_type = 'Loan type is required.';
  if (!f.employment_type) errs.employment_type = 'Employment type is required.';
  const age = Number(f.applicant_age);
  if (!f.applicant_age || isNaN(age) || age < 18 || age > 70) errs.applicant_age = 'Age must be between 18 and 70.';
  const income = Number(f.monthly_income);
  if (!f.monthly_income || isNaN(income) || income <= 0) errs.monthly_income = 'Monthly income must be a positive number.';
  const cibil = Number(f.cibil_score);
  if (!f.cibil_score || isNaN(cibil) || cibil < 300 || cibil > 900) errs.cibil_score = 'CIBIL score must be between 300 and 900.';
  const amt = Number(f.loan_amount_requested);
  if (!f.loan_amount_requested || isNaN(amt) || amt <= 0) errs.loan_amount_requested = 'Requested amount must be a positive number.';
  const tenure = Number(f.loan_tenure_months);
  if (!f.loan_tenure_months || isNaN(tenure) || tenure < 1 || tenure > 480) errs.loan_tenure_months = 'Tenure must be between 1 and 480 months.';
  if (['HOME', 'AUTO'].includes(f.loan_type)) {
    const pv = Number(f.property_value);
    if (!f.property_value || isNaN(pv) || pv <= 0) errs.property_value = 'Property/asset value is required for HOME and AUTO loans.';
  }
  if (f.existing_emi_amount && Number(f.existing_emi_amount) < 0) {
    errs.existing_emi_amount = 'Existing EMI cannot be negative.';
  }
  if (f.annual_interest_rate_percent) {
    const rate = Number(f.annual_interest_rate_percent);
    if (isNaN(rate) || rate <= 0 || rate > 100) {
      errs.annual_interest_rate_percent = 'Interest rate must be greater than 0 and at most 100.';
    }
  }
  const queryLength = f.query.trim().length;
  if (queryLength > 0 && queryLength < 5) errs.query = 'Additional context must be at least 5 characters.';
  if (queryLength > 2000) errs.query = 'Additional context cannot exceed 2,000 characters.';
  return errs;
}

function ResultPanel({ result, profile, onReset, onViewHarness }) {
  return (
    <Card style={{ marginTop: 0 }}>
      <CardHeader
        title="Indicative Assessment Result"
        subtitle={`Session: ${result.session_id?.slice(0, 12) || '—'}…`}
        right={
          <span style={{
            fontSize: 10, fontFamily: 'var(--font-mono)',
            background: '#FFF8F0', border: '1px solid #F5D5B3',
            color: 'var(--warning)', borderRadius: 4, padding: '2px 8px',
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}>Indicative Only</span>
        }
      />
      <CardBody>
        <Alert type="warning" style={{ marginBottom: 16 }}>
          This is an indicative assessment only and does not constitute a loan offer or approval.
          Final eligibility is subject to full credit appraisal, document verification, and bank
          underwriting policies at the time of formal application.
        </Alert>

        {/* Assessment narrative */}
        <div style={{
          background: 'var(--surface-inset)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '16px 18px', marginBottom: 20,
          fontSize: 13, lineHeight: 1.75, color: 'var(--text)',
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>
          {result.eligibility_assessment}
        </div>
        <RagQualityGate evaluation={result.rag_evaluation} citations={result.citations} />

        <SectionLabel>Submitted Profile</SectionLabel>
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr',
          gap: '8px 20px', marginBottom: 20,
        }}>
          {[
            ['Loan Type',        profile.loan_type],
            ['Employment',       profile.employment_type],
            ['Age',              `${profile.applicant_age} years`],
            ['Monthly Income',   formatINR(profile.monthly_income)],
            ['CIBIL Score',      profile.cibil_score],
            ['Existing EMI',     formatINR(profile.existing_emi_amount || 0)],
            ['Loan Requested',   formatINR(profile.loan_amount_requested)],
            ['Tenure',           `${profile.loan_tenure_months} months`],
            ...(profile.property_value ? [['Property Value', formatINR(profile.property_value)]] : []),
            ...(profile.annual_interest_rate_percent ? [['Interest Rate', `${profile.annual_interest_rate_percent}% p.a.`]] : []),
          ].map(([label, val]) => (
            <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 500 }}>{label}</span>
              <span style={{ fontSize: 13, color: 'var(--text)', fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{val}</span>
            </div>
          ))}
        </div>

        <Divider style={{ marginBottom: 16 }} />

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Btn variant="secondary" onClick={onReset}>Revise inputs</Btn>
          <Btn
            variant="ghost"
            onClick={onViewHarness}
          >
            View Control Panel →
          </Btn>
        </div>
      </CardBody>
    </Card>
  );
}

const INIT = {
  loan_type: 'HOME',
  applicant_age: '35',
  employment_type: 'SALARIED',
  monthly_income: '125000',
  cibil_score: '782',
  existing_emi_amount: '18000',
  loan_amount_requested: '4500000',
  loan_tenure_months: '240',
  property_value: '6500000',
  annual_interest_rate_percent: '8.75',
  query: 'Assess eligibility for a salaried applicant with stable income, good repayment history, and an existing EMI obligation.',
};

export default function LoanAssessmentPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState(INIT);
  const [errs, setErrs] = useState({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [apiErr, setApiErr] = useState('');

  const needsProperty = ['HOME', 'AUTO'].includes(form.loan_type);

  function set(field) {
    return e => {
      setForm(prev => ({ ...prev, [field]: e.target.value }));
      if (errs[field]) setErrs(prev => { const n = { ...prev }; delete n[field]; return n; });
    };
  }

  async function submit() {
    const v = validate(form);
    if (Object.keys(v).length) { setErrs(v); return; }
    setErrs({});
    setApiErr('');
    setLoading(true);

    const profile = {
      loan_type: form.loan_type,
      applicant_age: Number(form.applicant_age),
      employment_type: form.employment_type,
      monthly_income: Number(form.monthly_income),
      cibil_score: Number(form.cibil_score),
      existing_emi_amount: form.existing_emi_amount ? Number(form.existing_emi_amount) : 0,
      loan_amount_requested: Number(form.loan_amount_requested),
      loan_tenure_months: Number(form.loan_tenure_months),
      ...(needsProperty && form.property_value ? { property_value: Number(form.property_value) } : {}),
      ...(form.annual_interest_rate_percent ? { annual_interest_rate_percent: Number(form.annual_interest_rate_percent) } : {}),
    };

    try {
      const data = await api.loanAssess(profile, form.query.trim());
      setResult({ ...data, _profile: profile });
    } catch (e) {
      setApiErr(`Assessment failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setResult(null);
    setForm(INIT);
    setErrs({});
    setApiErr('');
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <AppNav active="/loan-assessment" />

      <div style={{ maxWidth: 820, margin: '0 auto', padding: '28px 20px 48px' }}>
        {/* Page header */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Loan Eligibility Assessment</div>
            <span style={{
              fontSize: 10, fontFamily: 'var(--font-mono)',
              background: 'var(--warning-bg)', border: '1px solid #F5D5B3',
              color: 'var(--warning)', borderRadius: 4, padding: '2px 8px',
              textTransform: 'uppercase', letterSpacing: '0.04em',
            }}>Indicative Only</span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
            The form is prefilled with a sample profile for a quick walkthrough. You can edit any value before running the assessment.
            This does not constitute a formal loan application or commitment.
          </div>
        </div>

        {result ? (
          <ResultPanel
            result={result}
            profile={result._profile}
            onReset={reset}
            onViewHarness={() => navigate('/dashboard')}
          />
        ) : (
          <Card>
            <CardHeader title="Applicant & Loan Details" />
            <CardBody>
              {apiErr && (
                <div style={{ marginBottom: 20 }}>
                  <Alert type="error">{apiErr}</Alert>
                </div>
              )}

              {/* Section: Loan */}
              <SectionLabel>Loan Parameters</SectionLabel>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px 20px', marginBottom: 24 }}>
                <FieldGroup label="Loan Type" htmlFor="loan_type" required error={errs.loan_type}>
                  <Select id="loan_type" value={form.loan_type} onChange={set('loan_type')} hasError={!!errs.loan_type}>
                    <option value="">Select loan type</option>
                    <option value="PERSONAL">Personal Loan</option>
                    <option value="HOME">Home Loan</option>
                    <option value="AUTO">Auto Loan</option>
                    <option value="BUSINESS">Business Loan</option>
                  </Select>
                </FieldGroup>

                <FieldGroup label="Loan Amount Requested (₹)" htmlFor="loan_amount_requested" required error={errs.loan_amount_requested}>
                  <Input id="loan_amount_requested" type="number" min="1" value={form.loan_amount_requested} onChange={set('loan_amount_requested')} hasError={!!errs.loan_amount_requested} placeholder="e.g. 4000000" />
                </FieldGroup>

                <FieldGroup label="Loan Tenure (months)" htmlFor="loan_tenure_months" required error={errs.loan_tenure_months} hint="1–480 months">
                  <Input id="loan_tenure_months" type="number" min="1" max="480" value={form.loan_tenure_months} onChange={set('loan_tenure_months')} hasError={!!errs.loan_tenure_months} placeholder="e.g. 240" />
                </FieldGroup>

                <FieldGroup label="Annual Interest Rate (%)" htmlFor="annual_interest_rate_percent" hint="Optional — enables EMI and FOIR calculation" error={errs.annual_interest_rate_percent}>
                  <Input id="annual_interest_rate_percent" type="number" step="0.01" min="0.01" max="100" value={form.annual_interest_rate_percent} onChange={set('annual_interest_rate_percent')} hasError={!!errs.annual_interest_rate_percent} placeholder="e.g. 8.5" />
                </FieldGroup>

                {needsProperty && (
                  <FieldGroup label="Property / Asset Value (₹)" htmlFor="property_value" required={needsProperty} error={errs.property_value}>
                    <Input id="property_value" type="number" min="1" value={form.property_value} onChange={set('property_value')} hasError={!!errs.property_value} placeholder="e.g. 6000000" />
                  </FieldGroup>
                )}
              </div>

              {/* Section: Applicant */}
              <SectionLabel>Applicant Profile</SectionLabel>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px 20px', marginBottom: 24 }}>
                <FieldGroup label="Age (years)" htmlFor="applicant_age" required error={errs.applicant_age} hint="18–70 years">
                  <Input id="applicant_age" type="number" min="18" max="70" value={form.applicant_age} onChange={set('applicant_age')} hasError={!!errs.applicant_age} placeholder="e.g. 35" />
                </FieldGroup>

                <FieldGroup label="Employment Type" htmlFor="employment_type" required error={errs.employment_type}>
                  <Select id="employment_type" value={form.employment_type} onChange={set('employment_type')} hasError={!!errs.employment_type}>
                    <option value="">Select employment type</option>
                    <option value="SALARIED">Salaried</option>
                    <option value="SELF_EMPLOYED">Self-employed</option>
                    <option value="BUSINESS_OWNER">Business Owner</option>
                  </Select>
                </FieldGroup>

                <FieldGroup label="Monthly Income (₹)" htmlFor="monthly_income" required error={errs.monthly_income}>
                  <Input id="monthly_income" type="number" min="1" value={form.monthly_income} onChange={set('monthly_income')} hasError={!!errs.monthly_income} placeholder="e.g. 100000" />
                </FieldGroup>

                <FieldGroup label="Existing Monthly EMI (₹)" htmlFor="existing_emi_amount" hint="Enter 0 if no existing EMIs" error={errs.existing_emi_amount}>
                  <Input id="existing_emi_amount" type="number" min="0" value={form.existing_emi_amount} onChange={set('existing_emi_amount')} hasError={!!errs.existing_emi_amount} placeholder="e.g. 15000" />
                </FieldGroup>

                <FieldGroup label="CIBIL Score" htmlFor="cibil_score" required error={errs.cibil_score} hint="300–900">
                  <Input id="cibil_score" type="number" min="300" max="900" value={form.cibil_score} onChange={set('cibil_score')} hasError={!!errs.cibil_score} placeholder="e.g. 750" />
                </FieldGroup>
              </div>

              {/* Optional context */}
              <SectionLabel>Additional Context (optional)</SectionLabel>
              <FieldGroup label="Assessment question or context" htmlFor="query" hint="Provide any specific question or context you'd like the assessment to address." error={errs.query}>
                <Textarea
                  id="query"
                  value={form.query}
                  onChange={set('query')}
                  rows={3}
                  maxLength={2000}
                  hasError={!!errs.query}
                  placeholder="e.g. I have a secondary income from rental property. How does that affect eligibility?"
                />
              </FieldGroup>

              {/* Disclaimer */}
              <div style={{
                marginTop: 20, padding: '10px 14px',
                background: 'var(--surface-inset)', border: '1px solid var(--border)',
                borderRadius: 6, fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6,
              }}>
                By submitting this form, you acknowledge that the assessment is indicative only.
                Assessment details and the resulting audit trail may be retained for review.
                Final eligibility is subject to underwriting policy.
              </div>

              <div style={{ marginTop: 20, display: 'flex', gap: 10, alignItems: 'center' }}>
                <Btn
                  variant="primary"
                  size="lg"
                  loading={loading}
                  disabled={loading}
                  onClick={submit}
                >
                  {loading ? 'Assessing…' : 'Request Indicative Assessment'}
                </Btn>
                <Btn
                  variant="ghost"
                  onClick={() => { setForm(INIT); setErrs({}); setApiErr(''); }}
                  disabled={loading}
                >
                  Reset sample
                </Btn>
              </div>
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
