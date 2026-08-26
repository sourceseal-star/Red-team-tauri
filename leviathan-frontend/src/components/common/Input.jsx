import React from 'react';
import '../../styles/index.css';

const Input = ({
  type = 'text',
  value,
  onChange,
  placeholder,
  disabled = false,
  className = '',
  label,
  error,
  ...props
}) => {
  return (
    <div className="form-group">
      {label && <label className="form-label">{label}</label>}
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        className={`form-control ${error ? 'is-invalid' : ''} ${className}`}
        {...props}
      />
      {error && <div className="invalid-feedback">{error}</div>}
    </div>
  );
};

export default Input;
