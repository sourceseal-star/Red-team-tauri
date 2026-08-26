import React from 'react';
import '../../styles/index.css';

const Button = ({
  children,
  onClick,
  disabled = false,
  type = 'button',
  className = '',
  variant = 'primary',
  size = 'md',
  icon,
  ...props
}) => {
  const baseClasses = 'btn';
  const variantClasses = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    success: 'btn-success',
    warning: 'btn-warning',
    danger: 'btn-danger',
    info: 'btn-info',
    light: 'btn-light',
    dark: 'btn-dark'
  };
  
  const sizeClasses = {
    sm: 'btn-sm',
    md: '',
    lg: 'btn-lg',
    icon: 'btn-icon'
  };

  return (
    <button
      type={type}
      className={`${baseClasses} ${variantClasses[variant] || ''} ${sizeClasses[size] || ''} ${className}`}
      onClick={onClick}
      disabled={disabled}
      {...props}
    >
      {icon && <span>{icon}</span>}
      {children}
    </button>
  );
};

export default Button;
