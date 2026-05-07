/**
 * Tests for Tooltip component, with focus on accessibility attributes.
 *
 * Verifies that the Tooltip component properly implements ARIA attributes
 * for screen reader compatibility and follows WAI-ARIA best practices.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Tooltip from './Tooltip'

describe('Tooltip component - accessibility attributes', () => {
  describe('ARIA attributes', () => {
    it('applies role="tooltip" to the tooltip element', () => {
      const { container } = render(
        <Tooltip text="Help text">
          <button>Trigger</button>
        </Tooltip>
      )

      // Tooltip is not visible by default
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()

      // Trigger visibility by focusing the wrapper
      const wrapper = container.firstChild
      wrapper.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }))

      const tooltip = screen.getByRole('tooltip')
      expect(tooltip).toBeInTheDocument()
      expect(tooltip).toHaveTextContent('Help text')
    })

    it('generates unique ID for tooltip element', () => {
      const { container: container1 } = render(
        <Tooltip text="First tooltip">
          <button>First</button>
        </Tooltip>
      )

      const { container: container2 } = render(
        <Tooltip text="Second tooltip">
          <button>Second</button>
        </Tooltip>
      )

      // Make tooltips visible
      container1.firstChild.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }))
      container2.firstChild.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }))

      const tooltip1 = container1.querySelector('[role="tooltip"]')
      const tooltip2 = container2.querySelector('[role="tooltip"]')

      expect(tooltip1).toHaveAttribute('id')
      expect(tooltip2).toHaveAttribute('id')
      expect(tooltip1.getAttribute('id')).not.toBe(tooltip2.getAttribute('id'))
    })

    it('does not apply aria-describedby when tooltip is hidden by default', () => {
      const { container } = render(
        <Tooltip text="Help text">
          <button>Trigger</button>
        </Tooltip>
      )

      const wrapper = container.firstChild
      expect(wrapper).not.toHaveAttribute('aria-describedby')
    })

    it('does not apply aria-describedby when text prop is not provided', () => {
      const { container } = render(
        <Tooltip>
          <button>Trigger</button>
        </Tooltip>
      )

      const wrapper = container.firstChild
      expect(wrapper).not.toHaveAttribute('aria-describedby')
    })
  })

  describe('tooltip rendering', () => {
    it('renders children correctly', () => {
      render(
        <Tooltip text="Help text">
          <button>Click me</button>
        </Tooltip>
      )

      expect(screen.getByRole('button')).toHaveTextContent('Click me')
    })

    it('renders tooltip text when provided', () => {
      const { container } = render(
        <Tooltip text="Helpful information">
          <button>Trigger</button>
        </Tooltip>
      )

      // Make tooltip visible
      container.firstChild.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }))

      expect(screen.getByRole('tooltip')).toHaveTextContent('Helpful information')
    })

    it('does not render tooltip when text prop is not provided', () => {
      const { container } = render(
        <Tooltip>
          <button>Trigger</button>
        </Tooltip>
      )

      const tooltip = container.querySelector('[role="tooltip"]')
      expect(tooltip).not.toBeInTheDocument()
    })
  })

  describe('positioning', () => {
    it('defaults to top position', () => {
      const { container } = render(
        <Tooltip text="Help text">
          <button>Trigger</button>
        </Tooltip>
      )

      // Make tooltip visible
      container.firstChild.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }))

      const tooltip = container.querySelector('[role="tooltip"]')
      const styles = tooltip.style

      expect(styles.bottom).toBe('calc(100% + 8px)')
      expect(styles.left).toBe('50%')
    })

    it('accepts custom position prop', () => {
      const { container } = render(
        <Tooltip text="Help text" position="bottom">
          <button>Trigger</button>
        </Tooltip>
      )

      // Make tooltip visible
      container.firstChild.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }))

      const tooltip = container.querySelector('[role="tooltip"]')
      const styles = tooltip.style

      expect(styles.top).toBe('calc(100% + 8px)')
      expect(styles.left).toBe('50%')
    })
  })
})
