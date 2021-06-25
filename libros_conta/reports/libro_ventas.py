from odoo import models, fields, api
import logging
from functools import lru_cache


class AccountInvoiceVentas(models.Model):
    _name = "account.invoice.libroventas"
    _description = "Invoices Statistics"
    _auto = False
    _rec_name = 'invoice_date_due'
    _order = 'invoice_date_due desc'

    # ==== Invoice fields ====
    vat = fields.Char(string='NIT', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Nombre', readonly=True)
    move_id = fields.Many2one('account.move', readonly=True, string="Factura")
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    invoice_date_due = fields.Date(string='Fecha de Vencimiento', readonly=True)
    move_type = fields.Selection([
        ('out_invoice', 'Factura'),
        ('in_invoice', 'Factura'),
        ('out_refund', 'Nota de Crédito'),
        ('in_refund', 'Nota de Crédito'),
        ], readonly=True, string="Tipo")
    
    mbase = fields.Float(readonly=True, string="Materiales Base")
    mimpuestos = fields.Float(readonly=True, string="Materiales Impuestos")
    sbase = fields.Float(readonly=True, string="Servicios Base")
    simpuestos = fields.Float(readonly=True, string="Servicios Impuestos")
    exportm = fields.Float(readonly=True, string="Exportación de Materiales")
    exports = fields.Float(readonly=True, string="Exportación de Servicios")

    _depends = {
        'account.move': [
            'name', 'state', 'move_type', 'partner_id', 'invoice_user_id', 'fiscal_position_id',
            'invoice_date', 'invoice_date_due', 'invoice_payment_term_id', 'partner_bank_id',
        ],
        'account.move.line': [
            'move_id', 'company_id',  'partner_id'
        ]
    }

    @property
    def _table_query(self):
        query = '%s %s %s' % (self._select(), self._from(), self._where())
        return query

    @api.model
    def _select(self):
        return '''
            SELECT
                id,
                vat,
                partner_id,
                move_id,
                company_id,
                move_type,
                invoice_date_due,
                mbase,
                mimpuestos,
                sbase,
                simpuestos
        '''

    @api.model
    def _from(self):
        return '''
            FROM 
            (
SELECT    
line.move_id AS id,
partner.vat,
line.partner_id,
line.move_id,
line.company_id,
move.move_type,
move.invoice_date_due,
SUM(CASE WHEN template.x_studio_bien_o_servicio = 'bien' THEN line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'out_refund' THEN -1 ELSE 1 END) AS mbase,
SUM(CASE WHEN template.x_studio_bien_o_servicio = 'bien' THEN line.price_total - line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'out_refund' THEN -1 ELSE 1 END) AS mimpuestos,
SUM(CASE WHEN COALESCE(template.x_studio_bien_o_servicio, '') <> 'bien' THEN line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'out_refund' THEN -1 ELSE 1 END) AS sbase,
SUM(CASE WHEN COALESCE(template.x_studio_bien_o_servicio, '') <> 'bien' THEN line.price_total - line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'out_refund' THEN -1 ELSE 1 END) AS simpuestos

FROM account_move_line line
LEFT JOIN res_partner partner ON partner.id = line.partner_id
INNER JOIN account_move move ON move.id = line.move_id
LEFT JOIN product_product product ON product.id = line.product_id
LEFT JOIN product_template template ON template.id = product.product_tmpl_id

WHERE 
      move.move_type IN ('out_invoice', 'out_refund')
      AND COALESCE(product.default_code, '') <> 'ISR RETENCIONES'
      AND NOT line.exclude_from_invoice_tab
      AND move.state NOT IN ('draft', 'cancel')
      
GROUP BY partner.vat, line.partner_id, line.move_id, line.company_id, move.move_type, move.invoice_date_due
            ) temptable
        '''
    
    @api.model
    def _where(self):
        return ''
