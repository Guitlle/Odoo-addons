from odoo import models, fields, api
import logging
from functools import lru_cache


class AccountInvoiceCompras(models.Model):
    _name = "account.invoice.librocompras"
    _description = "Libro Contable de Compras"
    _auto = False
    _rec_name = 'invoice_date_due'
    _order = 'invoice_date_due desc'
    
    # Depende de los campos adicionales:
    #    x_studio_bien_o_servicio  en el producto, que determina si es bien o servicio
    #    x_studio_serie  en la factura, el número de serie
    #    x_studio_regimen   en el proveedor, que puede ser pc para pequeño contribuyente o ret para sujeto a retenciones

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
    mpcbase = fields.Float(readonly=True, string="Materiales Pequeño Contribuyente")
    mpcimpuestos = fields.Float(readonly=True, string="Materiales PC Impuestos")
    spcbase = fields.Float(readonly=True, string="Servicios Pequeño Contribuyente")
    spcimpuestos = fields.Float(readonly=True, string="Servicios PC Impuestos")
    factura = fields.Char(string="Factura", readonly=True)
    serie = fields.Char(string="Serie", readonly=True)
    
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
                ref AS factura,
                x_studio_serie AS serie,
                move_type,
                invoice_date_due,
                mbase,
                mimpuestos,
                sbase,
                simpuestos,
                mpcbase,
                mpcimpuestos,
                spcbase,
                spcimpuestos
        '''

    @api.model
    def _from(self):
        return '''
          FROM 
          (
            SELECT    
              row_number() OVER () AS id,
              partner.vat,
              line.partner_id,
              line.move_id,
              line.company_id,
              move.move_type,
              move.ref,
              move.x_studio_serie,
              move.invoice_date_due,
              SUM(CASE WHEN template.x_studio_bien_o_servicio = 'bien' AND coalesce(partner.x_studio_regimen,'') <> 'pc' THEN line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'in_refund' THEN -1 ELSE 1 END) AS mbase,
              SUM(CASE WHEN template.x_studio_bien_o_servicio = 'bien' AND coalesce(partner.x_studio_regimen,'') <> 'pc'  THEN line.price_total - line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'in_refund' THEN -1 ELSE 1 END) AS mimpuestos,
              SUM(CASE WHEN (coalesce(template.x_studio_bien_o_servicio,'') <> 'bien')  AND coalesce(partner.x_studio_regimen,'') <> 'pc'  THEN line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'in_refund' THEN -1 ELSE 1 END) AS sbase,
              SUM(CASE WHEN (coalesce(template.x_studio_bien_o_servicio,'') <> 'bien') AND coalesce(partner.x_studio_regimen,'') <> 'pc' THEN line.price_total - line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'in_refund' THEN -1 ELSE 1 END) AS simpuestos,
              SUM(CASE WHEN template.x_studio_bien_o_servicio = 'bien' AND partner.x_studio_regimen = 'pc' THEN line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'in_refund' THEN -1 ELSE 1 END) AS mpcbase,
              SUM(CASE WHEN template.x_studio_bien_o_servicio = 'bien'  AND partner.x_studio_regimen = 'pc' THEN line.price_total - line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'in_refund' THEN -1 ELSE 1 END) AS mpcimpuestos,
              SUM(CASE WHEN (coalesce(template.x_studio_bien_o_servicio,'') <> 'bien')  AND partner.x_studio_regimen = 'pc' THEN line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'in_refund' THEN -1 ELSE 1 END) AS spcbase,
              SUM(CASE WHEN (coalesce(template.x_studio_bien_o_servicio,'') <> 'bien')  AND partner.x_studio_regimen = 'pc' THEN line.price_total - line.price_subtotal ELSE 0 END) * (CASE WHEN move.move_type = 'in_refund' THEN -1 ELSE 1 END) AS spcimpuestos


            FROM account_move_line line
              LEFT JOIN res_partner partner ON partner.id = line.partner_id
              INNER JOIN account_move move ON move.id = line.move_id
              LEFT JOIN product_product product ON product.id = line.product_id
              LEFT JOIN product_template template ON template.id = product.product_tmpl_id
              LEFT JOIN (
                SELECT * FROM account_move WHERE move_type = 'in_refund'
              ) refund ON refund.reversed_entry_id = move.id 
              
            WHERE move.move_type IN ('in_invoice', 'in_refund')
              AND COALESCE(product.default_code, '') <> 'ISR RETENCIONES'
              AND NOT line.exclude_from_invoice_tab
              AND move.state NOT IN ('draft', 'cancel')
              AND COALESCE(move.x_studio_caja_chica, FALSE) = FALSE
              AND 
                ( COALESCE(move.x_studio_nota_de_crdito_interna, FALSE) = FALSE AND COALESCE(refund.x_studio_nota_de_crdito_interna, FALSE) = FALSE)
            
            GROUP BY partner.vat, line.partner_id, line.move_id, line.company_id, move.move_type, move.invoice_date_due, move.ref, move.x_studio_serie
            
          ) temptable
        '''
    
    @api.model
    def _where(self):
        return ''
