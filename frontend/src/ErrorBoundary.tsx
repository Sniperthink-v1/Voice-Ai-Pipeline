import { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: any;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('ErrorBoundary caught:', error, errorInfo);
    this.setState({ error, errorInfo });
    
    // Send to remote logging if available
    this.sendErrorReport(error, errorInfo);
  }

  sendErrorReport(error: Error, errorInfo: any) {
    const report = {
      timestamp: new Date().toISOString(),
      error: {
        message: error.message,
        stack: error.stack,
      },
      errorInfo,
      userAgent: navigator.userAgent,
      url: window.location.href,
    };

    console.error('Error Report:', JSON.stringify(report, null, 2));

    // You can send this to a logging service
    // For now, just store it in localStorage for later retrieval
    try {
      const existingErrors = JSON.parse(localStorage.getItem('error_reports') || '[]');
      existingErrors.push(report);
      localStorage.setItem('error_reports', JSON.stringify(existingErrors.slice(-10)));
    } catch (e) {
      console.error('Failed to store error report:', e);
    }
  }

  copyErrorReport = () => {
    const report = {
      error: this.state.error?.message,
      stack: this.state.error?.stack,
      componentStack: this.state.errorInfo?.componentStack,
      userAgent: navigator.userAgent,
    };
    
    const text = JSON.stringify(report, null, 2);
    navigator.clipboard.writeText(text).then(() => {
      alert('Error report copied to clipboard!');
    }).catch(() => {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      alert('Error report copied!');
    });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          backgroundColor: '#fef2f2',
          minHeight: '100vh',
        }}>
          <h1 style={{ color: '#dc2626', marginBottom: '20px' }}>
            ⚠️ Something went wrong
          </h1>
          <p style={{ color: '#991b1b', marginBottom: '20px' }}>
            The application encountered an error. Please copy the error report and share it with the developer.
          </p>
          
          <div style={{
            backgroundColor: '#1f2937',
            color: '#f3f4f6',
            padding: '20px',
            borderRadius: '8px',
            textAlign: 'left',
            maxWidth: '800px',
            margin: '0 auto 20px',
            overflow: 'auto',
            fontFamily: 'monospace',
            fontSize: '12px',
          }}>
            <p><strong>Error:</strong> {this.state.error?.message}</p>
            <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
              {this.state.error?.stack}
            </pre>
          </div>

          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              onClick={this.copyErrorReport}
              style={{
                padding: '12px 24px',
                backgroundColor: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '14px',
              }}
            >
              📋 Copy Error Report
            </button>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '12px 24px',
                backgroundColor: '#10b981',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '14px',
              }}
            >
              🔄 Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
