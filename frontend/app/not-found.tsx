import Link from 'next/link';

export default function NotFound() {
  return (
    <div style={{
      textAlign: 'center',
      padding: '100px 20px',
      color: '#fff',
      backgroundColor: '#0B0F19',
      minHeight: '80vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <h1 style={{ fontSize: '72px', fontWeight: 800, margin: 0, color: '#3B82F6' }}>404</h1>
      <h2 style={{ fontSize: '24px', margin: '16px 0 24px' }}>Không tìm thấy trang yêu cầu</h2>
      <p style={{ color: '#94A3B8', maxWidth: '500px', marginBottom: '32px', lineHeight: 1.6 }}>
        Thủ tục hành chính hoặc đường dẫn này hiện không tồn tại hoặc đã được cập nhật sang mã thủ tục mới.
      </p>
      <Link href="/thu-tuc" style={{
        display: 'inline-block',
        backgroundColor: '#2563EB',
        color: '#fff',
        padding: '12px 28px',
        borderRadius: '8px',
        textDecoration: 'none',
        fontWeight: 600,
        boxShadow: '0 4px 14px rgba(37, 99, 235, 0.4)'
      }}>
        Quay lại Danh sách Thủ tục
      </Link>
    </div>
  );
}
