import React from 'react';
import '../../styles/index.css';

const Badge = ({
  children,
  variant = 'primary',
  className = '',
  pill = false,
  ...props
}) => {
  const variantClasses = {
    primary: 'badge-primary',
    secondary: 'badge-secondary',
    success: 'badge-success',
    warning: 'badge-warning',
    danger: 'badge-danger',
    info: 'badge-info',
    light: 'badge-light',
    dark: 'badge-dark'
  };

  return (
    <span
      className={`badge ${variantClasses[variant] || ''} ${pill ? 'badge-pill' : ''} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
};

export default Badge;
